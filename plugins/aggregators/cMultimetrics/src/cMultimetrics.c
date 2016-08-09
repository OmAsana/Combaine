#include <Python.h>
#include "structmember.h"
#include <stdbool.h>

typedef struct {
    PyObject_HEAD
    //PyObject *log; /* substrings in metric name for determine timings */

    int *quantile ; /* quantile list */
    char *timings_is; /* substrings in metric name for determine timings */
    int factor;
    int rps;
    int get_prc;
} cMultimetrics;

static void cMultimetrics_dealloc(cMultimetrics* self)
{
    // XXX: TODO:
    //Py_XDECREF(self->quantile);
    //Py_XDECREF(self->timings_is);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
cMultimetrics_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    cMultimetrics *self;

    self = (cMultimetrics *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->timings_is = "_timings";

        // XXX: TODO build quantile
        //self->quantile = PyString_FromString("");

        self->factor = 1;
        self->rps = true;
        self->get_prc = 0;
    }

    return (PyObject *)self;
}

static int
cMultimetrics_init(cMultimetrics *self, PyObject *args, PyObject *kwds)
{
    char * value;
    PyObject *tmp;
    PyObject *config = NULL;   // PyDictObject

    if (! PyArg_ParseTuple(args, "O", &config))
        return -1;
    if (! PyDict_Check(config)){
        PyErr_SetString(PyExc_TypeError, "__init__ argument must be dict type");
        return -1;
    }

    if (config) {
        tmp = PyDict_GetItemString(config, "timings_is");
        if (tmp){
            value = PyString_AsString(tmp);
            if (value)
                self->timings_is = PyString_AsString(tmp);
        }
        tmp = PyDict_GetItemString(config, "rps");
        if (tmp) {
            if (PyInt_Check(tmp)){
                self->rps = (bool)PyInt_AS_LONG(tmp);
            } else {
                if (PyString_Check(tmp)) {
                    value = PyString_AsString(tmp);
                } else {
                    PyErr_SetString(PyExc_TypeError,
                                    "rps should be yes/True or no/False");
                    return -1;
                }
                if (value && (strcmp(value, "yes") != 0))
                    self->rps = false;
            }


        }
    }
    return 0;
}

static PyObject *
cMultimetrics_repr(cMultimetrics *self){
    static PyObject *format = NULL;
    PyObject *args, *repr;

    format = PyString_FromString("<%s({'timings_is': '%s', 'rps': %d, "
                                 "'factor': %d... })>");
    args = Py_BuildValue("ssii", self->ob_type->tp_name,
                         self->timings_is,
                         self->rps,
                         self->factor);
    repr = PyString_Format(format, args);
    return repr;
}


static PyObject *
cMultimetrics_aggregate_host(cMultimetrics* self)
{
    static PyObject *format = NULL;
    PyObject *args, *result;

    if (format == NULL) {
        format = PyString_FromString("%s -> %s :-)");
        if (format == NULL)
            return NULL;
    }

    args = Py_BuildValue("ss", "aggregate_host say", self->timings_is);
    if (args == NULL)
        return NULL;

    result = PyString_Format(format, args);
    Py_DECREF(args);

    return result;
}

static PyObject *
cMultimetrics_aggregate_group(cMultimetrics* self)
{
    static PyObject *format = NULL;
    PyObject *result;

    if (format == NULL) {
        format = PyString_FromString("aggregate_group: %s");
        if (format == NULL)
            return NULL;
    }
    result = PyString_Format(format, PyString_FromString(self->timings_is));

    return result;
}

static PyMethodDef cMultimetrics_methods[] = {
    {"aggregate_host", (PyCFunction)cMultimetrics_aggregate_host, METH_NOARGS,
     "Make aggregation for single host"
    },
    {"aggregate_group", (PyCFunction)cMultimetrics_aggregate_group, METH_NOARGS,
     "Make aggregation group of hosts"
    },
    {NULL}  /* Sentinel */
};


static PyTypeObject cMultimetricsType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "cMultimetrics.cMultimetrics",  /*tp_name*/
    sizeof(cMultimetrics),           /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)cMultimetrics_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    (reprfunc)cMultimetrics_repr,  /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,        /*tp_flags*/
    "C Multimetrics objects",  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    cMultimetrics_methods,     /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)cMultimetrics_init,      /* tp_init */
    0,                         /* tp_alloc */
    cMultimetrics_new,                 /* tp_new */
};

static PyMethodDef multimetrics_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initcMultimetrics(void)
{
    PyObject* m;

    if (PyType_Ready(&cMultimetricsType) < 0)
        return;

    m = Py_InitModule3("cMultimetrics", multimetrics_methods,
                       "Example module that creates an extension type.");

    if (m == NULL)
      return;

    Py_INCREF(&cMultimetricsType);
    PyModule_AddObject(m, "cMultimetrics", (PyObject *)&cMultimetricsType);
}
