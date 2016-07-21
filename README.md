Neurons
=======

Neurons is an opinionated web framework built on Spyne, Twisted and SqlAlchemy.

Running tests
=============

Here's how to get a test environment up and running:

First, create a virtualenv:

    virtualenv -p python2.7 virt-2.7
    source virt-2.7/bin/activate

If you want to work on Spyne's development version, clone spyne:

    git clone git://github.com/plq/spyne
    (cd spyne; python setup.py develop)

Now clone neurons:

    git clone git://github.com/plq/neurons
    (cd neurons; python setup.py develop)

Install useful packages:

    pip install ipython\<5 pytest ipdb pytest-twisted

And now try:

    py.test -v neurons/neurons

works great here.

If you want to inspect the html output in a browser, run ``make`` in
``neurons/asssets`` to get relevant frontend libraries.
