from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.misc.arrayTools import unionRect
from fontTools.pens.cairoPen import CairoPen

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

COLORS = [(1,0,0), (0,0,1)]


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

    cr.scale(width / (w + 2 * margin), height / (h + 2 * margin))
    cr.translate(margin - bounds[0], margin + bounds[3])
    cr.scale(1, -1)

    cr.save()
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
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()

    cr.restore()


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
