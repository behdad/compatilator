from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.misc.arrayTools import unionRect
from fontTools.pens.cairoPen import CairoPen

from dataclasses import dataclass

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

COLORS = [(1,0,0), (0,0,1)]


@dataclass
class Segment:
    pos: complex
    vec: complex

    def __len__(self):
        return abs(self.vec)


def render(fonts, glyphname, cr, width, height):

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

    paths = []
    for glyph,glyphset in zip(glyphs,glyphsets):
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
