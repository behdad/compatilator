from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.misc.arrayTools import unionRect
from fontTools.pens.cairoPen import CairoPen

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

COLORS = [(1,0,0), (0,0,1)]


def render(fonts, glyphname, context, width, height):

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

    context.scale(width / (w + 2 * margin), height / (h + 2 * margin))
    context.translate(margin - bounds[0], margin + bounds[3])
    context.scale(1, -1)

    context.save()
    for glyph,glyphset,color in zip(glyphs,glyphsets,COLORS):
        pen = CairoPen(glyphset, context)
        glyph.draw(pen)
        context.set_source_rgb(*color)
        context.stroke()
    context.restore()


def main(font1, font2, glyphname=None):

    global fonts
    fonts = [TTFont(path) for path in (font1, font2)]

    def on_draw(da, context):
        alloc = da.get_allocation()
        render(fonts, glyphname, context, alloc.width, alloc.height)

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
