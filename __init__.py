from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.misc.arrayTools import unionRect
from fontTools.misc.bezierTools import calcQuadraticArcLengthC, splitCubicAtTC, splitQuadraticAtT
from fontTools.pens.cairoPen import CairoPen

import sys
import math
import functools
from dataclasses import dataclass

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

COLORS = [(.8,0,0), (0,0,.8), (0,.8,0)]


@dataclass
class Curve:
    p0: complex
    p1: complex
    p2: complex

    def asCubic(self):
        p0 = self.p0
        p1 = self.p1
        p2 = self.p2
        return p0,p0+(p1-p0)*2/3,p2+(p1-p2)*2/3,p2

    def length(self):
        return calcQuadraticArcLengthC(self.p0, self.p1, self.p2)

    def turn(self):
        vec = self.p1 - self.p0
        angle1 = math.atan2(vec.real, vec.imag)
        vec = self.p2 - self.p1
        angle2 = math.atan2(vec.real, vec.imag)
        diff = angle2 - angle1
        if diff > math.pi:
            diff -= 2 * math.pi
        elif diff < -math.pi:
            diff += 2 * math.pi
        return diff

@dataclass
class Corner:
    pl: complex # last point
    p0: complex # corner point
    p1: complex # next point

    def asCubic(self):
        p0 = self.p0
        return p0,p0,p0,p0

    def length(self):
        return 0

    def turn(self):
        vec = self.p0 - self.pl
        angle1 = math.atan2(vec.real, vec.imag)
        vec = self.p1 - self.p0
        angle2 = math.atan2(vec.real, vec.imag)
        diff = angle2 - angle1
        if diff > math.pi:
            diff -= 2 * math.pi
        elif diff < -math.pi:
            diff += 2 * math.pi
        return diff

def cost(part, whole, n):
    return abs(part.turn() - whole.turn() / n)

sys.setrecursionlimit(10000)

sol = {}

@functools.cache
def dp(i, j):
    global o1, o2, n1, n2, sol

    if i == 0 and j == 0:
        return 0

    ret = math.inf

    if i and j:

        lookback = 5

        for k in range(i - 1, max(0, i - lookback) - 1, -1):
            s = 0
            for l in range(k, i):
                s += cost(o1[l], o2[j - 1], i - k)
            ss = dp(k, j - 1) + s
            if ss < ret:
                ret = ss
                sol[(i, j)] = (k, j - 1)

        for k in range(j - 1, max(0, j - lookback) - 1, -1):
            s = 0
            for l in range(k, j):
                s += cost(o2[l], o1[i - 1], j - k)
            ss = dp(i - 1, k) + s
            if ss < ret:
                ret = ss
                sol[(i, j)] = (i - 1, k)

    return ret

def solve():

    global outlines

    # Rotate outlines to have point with one extrema first XXX
    new_outlines = []
    for outline in outlines:
        i = min(range(len(outline)), key=lambda j: outline[j].p0.real)
        new_outlines.append(outline[i:]+outline[:i])
    outlines = new_outlines
    del new_outlines

    global o1, o2, n1, n2
    o1, o2 = outlines
    n1, n2 = len(o1), len(o2)
    return dp(len(o1), len(o2))


def render(fonts, glyphname, cr, width, height):

    global outlines

    glyphsets = [font.getGlyphSet() for font in fonts]
    glyphs = [glyphset[glyphname] for glyphset in glyphsets]

    # Scale canvas

    bounds = None
    for glyph,glyphset in zip(glyphs,glyphsets):
        pen = ControlBoundsPen(glyphset)
        glyph.draw(pen)
        if bounds is None:
            bounds = pen.bounds
        else:
            bounds = unionRect(bounds, pen.bounds)
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    margin = max(w, h) * .1
    mult = min(width / (w + 2 * margin), height / (h + 2 * margin))

    cr.translate((width - mult * (w + 2 * margin)) * .5,
                 (height - mult * (h + 2 * margin)) * .5)
    cr.scale(mult, mult)
    cr.translate(margin - bounds[0], margin + bounds[3])
    cr.scale(1, -1)

    cr.save()
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for glyph,glyphset,color in zip(glyphs,glyphsets,COLORS):
        cr.set_source_rgb(*color)

        pen = CairoPen(glyphset, cr)
        glyph.draw(pen)
        cr.set_line_width(2)
        cr.stroke()

        pen = RecordingPointPen()
        glyph.drawPoints(pen)
        for command in pen.value:
            if command[0] != 'addPoint':
                continue
            pt = command[1][0]
            cr.move_to(*pt)
            cr.line_to(*pt)
        cr.set_line_width(5)
        cr.stroke()
    cr.restore()

    # Collect outlines

    recordings = []
    for glyph in glyphs:
        r = RecordingPen()
        glyph.draw(r)
        recordings.append(r.value)

    curves = []
    for rec in recordings:
        curve = []
        curves.append(curve)
        startPt = currentPt = None
        for op,args in rec:
            if op == 'moveTo':
                startPt = currentPt = complex(*args[0])
            elif op == 'closePath':
                if currentPt != startPt:
                    midPt = (currentPt + startPt) * .5
                    curve.append(Curve(p0 = currentPt, p1 = midPt, p2 = startPt))
                startPt = currentPt = None
            elif op == 'lineTo':
                p1 = complex(*args[0])
                midPt = (currentPt + p1) * .5
                curve.append(Curve(p0 = currentPt, p1 = midPt, p2 = p1))
                currentPt = p1
            elif op == 'qCurveTo':
                # Split curve into fixed number of segments
                n = 1
                p0 = currentPt.real,currentPt.imag
                p1 = args[0]
                p2 = args[1]
                ts = [i / n for i in range(1, n)]
                parts = splitQuadraticAtT(p0, p1, p2, *ts)
                for part in parts:
                    curve.append(Curve(p0 = complex(*part[0]),
                                       p1 = complex(*part[1]),
                                       p2 = complex(*part[2])))
                currentPt = complex(*p2)
            elif op == 'curveTo':
                raise NotImplementedError

    outlines = []
    for curve in curves:
        segments = []
        outlines.append(segments)
        for i in range(len(curve)):
            c = curve[i]
            l = curve[i - 1]

            # Add the corner segment
            segments.append(Corner(l.p1, c.p0, c.p1))

            # Add the curve segment

            segments.append(c)


    ret = solve()
    print(ret)

    # Draw solution

    if True:
        o1, o2 = outlines
        cr.set_line_width(2)
        cr.set_source_rgb(*COLORS[2])
        for t in (.7,):
            cr.new_path()
            cur = len(o1), len(o2)
            while cur[0] or cur[1]:

                next_cur = sol[cur]
                assert cur[0] - next_cur[0] == 1 or cur[1] - next_cur[1] == 1

                #print()
                #print(o1[next_cur[0]:cur[0]])
                #print(o2[next_cur[1]:cur[1]])
                cs1 = [c.asCubic() for c in o1[next_cur[0]:cur[0]]]
                cs2 = [c.asCubic() for c in o2[next_cur[1]:cur[1]]]
                assert len(cs1) == 1 or len(cs2) == 1
                swapped = False
                if len(cs1) != 1:
                    swapped = True
                    cs1, cs2 = cs2, cs1

                # Split cs1 to len(cs2) segments at equal t's
                n = len(cs2)
                ts = [i / n for i in range(1, n)]
                cs1 = list(splitCubicAtTC(*cs1[0], *ts))
                assert len(cs1) == len(cs2)

                if swapped:
                    cs1, cs2 = cs2, cs1

                for c1, c2 in zip(cs1, cs2):
                    ps = c1
                    qs = c2
                    rs = tuple(p + (q - p) * t for p,q in zip(ps,qs))
                    cr.move_to(rs[0].real, rs[0].imag)
                    cr.curve_to(rs[1].real, rs[1].imag,
                                rs[2].real, rs[2].imag,
                                rs[3].real, rs[3].imag)

                cur = next_cur

            cr.close_path()
            cr.stroke()

    if False:
        o1, o2 = outlines
        cr.set_line_width(1)
        cr.set_source_rgb(*COLORS[2])
        for t in (.25, .5, .75):
            cr.new_path()
            cur = len(o1), len(o2)
            while cur[0] or cur[1]:

                p = o1[cur[0] - 1].p0
                q = o2[cur[1] - 1].p0
                cr.move_to(p.real, p.imag)
                cr.line_to(q.real, q.imag)

                cur = sol[cur]

            cr.stroke()



def main(font1, font2, glyphname=None):

    global fonts
    fonts = [TTFont(path) for path in (font1, font2)]

    def on_draw(da, cr):
        alloc = da.get_allocation()
        render(fonts, glyphname, cr, alloc.width, alloc.height)

    drawingarea = Gtk.DrawingArea()
    drawingarea.connect("draw", on_draw)

    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.connect("key-press-event", Gtk.main_quit)
    win.set_default_size(1000, 700)
    win.add(drawingarea)

    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compatilator.")
    parser.add_argument("font1", help="first font file")
    parser.add_argument("font2", help="second font file")
    parser.add_argument("glyphname", help="glyph name to work on")
    args = parser.parse_args()
    main(args.font1, args.font2, args.glyphname)
