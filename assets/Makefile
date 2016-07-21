
all: jquery-1.11.1 jquery-ui-1.11.0 jquery-timepicker bootstrap-3.2.0

jquery-1.11.1:
	mkdir $@; cd $@; wget https://code.jquery.com/$@.min.js -O jquery-min.js

jquery-ui-1.11.0:
	mkdir $@; cd $@; wget http://jqueryui.com/resources/download/$@.zip; \
	    unzip $@.zip; mv $@/* .; rm -rf $@ $@.zip external index.html;

jquery-timepicker:
	mkdir $@; cd $@; wget http://trentrichardson.com/examples/timepicker/jquery-ui-timepicker-addon.js; \
			 wget http://trentrichardson.com/examples/timepicker/jquery-ui-timepicker-addon.css

bootstrap-3.2.0:
	mkdir $@; cd $@; wget https://github.com/twbs/bootstrap/releases/download/v3.2.0/bootstrap-3.2.0-dist.zip -O $@.zip; \
	    unzip $@.zip; mv $@*/* .; rm -rf $@*

clean:
	-rm -rf jquery-*
