DRAWIO?=drawio

PNG := $(patsubst %.drawio,%.png,$(wildcard images/*.drawio))
SVG := $(patsubst %.drawio,%.svg,$(wildcard images/*.drawio))
PDF := $(patsubst %.drawio,%.pdf,$(wildcard images/*.drawio))



%.png : %.drawio
	$(DRAWIO) -x -f png  $<
%.pdf : %.drawio
	$(DRAWIO) -x -f pdf  $<
%.svg : %.drawio
	$(DRAWIO) -x -f svg  $<


all_images: $(PNG) $(SVG) $(PDF)
