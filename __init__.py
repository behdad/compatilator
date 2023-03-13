from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.misc.arrayTools import unionRect
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
class Segment:
    pos: complex
    vec: complex

    def __abs__(self):
        return abs(self.vec)

    def cost(self, other):
        angle1 = math.atan2(self.vec.real, self.vec.imag)
        angle2 = math.atan2(other.vec.real, other.vec.imag)

        return abs(angle1 - angle2) ** .5 * abs(self.vec)
        #return abs(other.vec - self.vec)
        #return (abs(other.vec - self.vec) / max(abs(other.vec), abs(self.vec)))

sys.setrecursionlimit(10000)

sol = {}

@functools.cache
def dp(i, j):
    global o1, o2, n1, n2, sol

    if i == 0 and j == 0:
        return 0

    ret = math.inf

    if i and j:

        lookback = 10

        s = 0
        for k in range(i - 1, max(j - 1, i - lookback) - 1, -1):
            s = s + o1[k].cost(o2[j - 1])
            ss = dp(k, j - 1) + s + abs((k / n1) - (j-1) / n2) ** .5 * math.pi
            if ss < ret:
                ret = ss
                sol[(i, j)] = (k, j - 1)

        s = 0
        for k in range(j - 1, max(i - 1, j - lookback) - 1, -1):
            s = s + o1[i - 1].cost(o2[k])
            ss = dp(i - 1, k) + s / (j - k) + abs((k / n1) - (j-1) / n2) ** .5 * math.pi
            if ss < ret:
                ret = ss
                sol[(i, j)] = (i - 1, k)

    return ret

def solve():

    global outlines

    # Rotate outlines to have point with one extrema first XXX
    new_outlines = []
    for outline in outlines:
        i = min(range(len(outline)), key=lambda j: outline[j].pos.real)
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

    # Collect outlines from cairo paths

    paths = []
    for glyph,glyphset in zip(glyphs,glyphsets):
        cr.new_path()
        pen = CairoPen(glyphset, cr)
        glyph.draw(pen)
        paths.append(cr.copy_path_flat())

    outlines = []
    for path in paths:
        outline = []
        outlines.append(outline)
        for tp, pts in path:
            if tp == cairo.PATH_MOVE_TO:
                first = last = complex(*pts)
            elif tp == cairo.PATH_LINE_TO:
                pt = complex(*pts)
                outline.append(Segment(last, pt - last))
                last = pt
            elif tp == cairo.PATH_CLOSE_PATH:
                if last != first:
                    outline.append(Segment(last, first - last))
                first = last = None
            else:
                assert False, tp

    # Uniform parametrization of outlines
    new_outlines = []
    tolerance = 4 # cr.get_tolerance() * 5
    for outline in outlines:
        new_outline = []
        new_outlines.append(new_outline)
        for segment in outline:
            n = math.ceil(abs(segment) / tolerance)
            inc = segment.vec / n
            pos = segment.pos
            for i in range(n):
                new_outline.append(Segment(pos, inc))
                pos += inc
    outlines = new_outlines
    del new_outlines

    ret = solve()
    print(ret)

    # Draw solution

    if True:
        o1, o2 = outlines
        cr.set_line_width(2)
        cr.set_source_rgb(*COLORS[2])
        for t in (.25, .5, .75):
            cr.new_path()
            cur = len(o1), len(o2)
            while cur[0] or cur[1]:

                p0 = o1[cur[0] - 1].pos
                p1 = o2[cur[1] - 1].pos
                p = p0 + (p1 - p0) * t
                cr.line_to(p.real, p.imag)

                cur = sol[cur]

            cr.close_path()
            cr.stroke()

    if False:
        o1, o2 = outlines
        cr.set_line_width(1)
        cr.set_source_rgb(*COLORS[2])
        for t in (.25, .5, .75):
            cr.new_path()
            i = 0
            cur = len(o1), len(o2)
            while cur[0] or cur[1]:

                p0 = o1[cur[0] - 1].pos
                p1 = o2[cur[1] - 1].pos
                p = p0 + (p1 - p0) * t

                if i % 16 == 0:
                    cr.move_to(p0.real, p0.imag)
                    cr.line_to(p1.real, p1.imag)
                    cr.stroke()

                i += 1
                cur = sol[cur]

    # Draw outline angle function

    mag = 16
    x0 = 0
    x1 = 100
    y0 = bounds[1]

    if True:
        for i,(outline,color) in enumerate(zip(outlines,COLORS)):
            cr.set_source_rgb(*color)
            x = x0 + i * x1
            y = y0
            yinc = (bounds[3] - bounds[1]) / len(outline)
            cr.new_path()
            for segment in outline:
                angle = math.atan2(segment.vec.real, segment.vec.imag)
                cr.line_to(x + angle * mag, y)
                y += yinc
            cr.stroke()

    if True:
        o1, o2 = outlines
        cr.set_line_width(1)
        cr.set_source_rgb(*COLORS[2])
        cr.new_path()
        i = 0
        height = bounds[3] - bounds[1]
        cur = len(o1), len(o2)
        while cur[0] or cur[1]:

            seg1 = o1[cur[0] - 1]
            seg2 = o2[cur[1] - 1]
            angle1 = math.atan2(seg1.vec.real, seg1.vec.imag)
            angle2 = math.atan2(seg2.vec.real, seg2.vec.imag)

            if i % 16 == 0:
                cr.move_to(x0 + angle1 * mag, y0 + (cur[0] - 1) * height / len(o1))
                cr.line_to(x0 + x1 + angle2 * mag, y0 + (cur[1] - 1) * height / len(o2))
                cr.stroke()

            i += 1
            cur = sol[cur]



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
