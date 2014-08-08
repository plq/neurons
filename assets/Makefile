
all: jquery-1.11.1 jquery-ui-1.11.0

jquery-%:
	mkdir $@; cd $@; wget https://code.jquery.com/jquery-1.11.0.min.js -O jquery-min.js

jquery-ui-%:
	mkdir $@; cd $@; wget http://jqueryui.com/resources/download/$@.zip; unzip $@.zip; mv $@/* .; rm -rf $@ $@.zip external index.html;

clean:
	-rm -rf jquery-*