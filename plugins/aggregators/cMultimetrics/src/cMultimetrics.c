#include <Python.h>
#include "structmember.h"
#include <stdbool.h>

typedef struct {
    PyObject_HEAD
    //PyObject *log;  /* python function logger */
    char        *timings_is; /* substrings in metric name for determine timings */
    bool        rps;
    bool        get_prc;
    int         factor;
    int         *quantile; /* quantile list */
    Py_ssize_t  quantile_size;
} cMultimetrics;

static int default_quantiles[] = {75, 90, 93, 94, 95, 96, 97, 98, 99};

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
        self->factor = 1;
        self->rps = true;
        self->get_prc = false;
        self->quantile = default_quantiles;
        self->quantile_size = sizeof(default_quantiles)/sizeof(int);
    }

    return (PyObject *)self;
}

static int
cMultimetrics_init(cMultimetrics *self, PyObject *args, PyObject *kwds)
{
    char * value;
    PyObject *tmp;
    PyObject *config = NULL;   // PyDictObject

    if (! PyArg_ParseTuple(args, "O", &config)) {
        return -1;
    }
    if (! PyDict_Check(config)){
        PyErr_SetString(PyExc_TypeError, "__init__ argument must be dict type");
        return -1;
    }

    if (!config) {
        return -1;
    }

    tmp = PyDict_GetItemString(config, "timings_is");
    if (tmp){
        value = PyString_AsString(tmp);
        if (!value){
            return -1;
        }

        self->timings_is = PyString_AsString(tmp);
    }

    tmp = PyDict_GetItemString(config, "rps");
    if (tmp) {
        if (PyInt_Check(tmp)){
            self->rps = (bool)PyInt_AS_LONG(tmp);
        } else {
            if (!PyString_Check(tmp)) {
                PyErr_SetString(PyExc_TypeError,
                                "rps should be yes/True or no/False");
                return -1;
            }

            value = PyString_AsString(tmp);
            if (value && (strcmp(value, "yes") != 0)) {
                self->rps = false;
            }
        }
    }
    tmp = PyDict_GetItemString(config, "get_prc");
    if (tmp) {
        if (PyInt_Check(tmp)){
            self->get_prc = (bool)PyInt_AS_LONG(tmp);
        } else {
            if (!PyString_Check(tmp)) {
                PyErr_SetString(PyExc_TypeError,
                                "get_prc should be yes/True or no/False");
                return -1;
            }

            value = PyString_AsString(tmp);
            // by default get_prc is false
            if (value && (strcmp(value, "yes") == 0)) {
                self->get_prc = true;
            }
        }
    }

    tmp = PyDict_GetItemString(config, "factor");
    if (tmp) {
        if (!PyInt_Check(tmp)){
            PyErr_SetString(PyExc_TypeError, "factor argument expect int");
            return -1;
        }
        self->factor = PyInt_AS_LONG(tmp);
    }

    tmp = PyDict_GetItemString(config, "quantile");
    if (tmp) {
        if (!PyList_CheckExact(tmp)){
            PyErr_SetString(PyExc_TypeError, "quantile argument expect list");
            return -1;
        }
        Py_ssize_t len = PyList_GET_SIZE(tmp);
        if (len > 100){
            PyErr_SetString(PyExc_ValueError, "upto 100 quantilies allowed");
            return -1;
        }

        int *new_quantile = calloc(sizeof(int), len);
        for (Py_ssize_t i = 0; i < len; i++) {
            PyObject *v = PyList_GET_ITEM(tmp, i);
            if (!PyInt_CheckExact(v)){
                free(new_quantile);
                PyErr_SetString(PyExc_ValueError,
                                "quantile argument expect list of integers");
                return -1;
            }
            long int q = PyInt_AS_LONG(v);
            if (q < 0 || q > 100){
                free(new_quantile);
                PyErr_SetString(PyExc_ValueError,
                                "quantile value out of range {0..100}");
                return -1;
            }
            new_quantile[i] = (int)q;
        }
        self->quantile_size = len;

        // For sorting
        int my_cmp (const void * a, const void * b) {
           return (*(int*)a - *(int*)b);
        }
        qsort(new_quantile, len, sizeof(int), my_cmp);

        int *old_quantile = self->quantile;
        if (old_quantile && old_quantile != default_quantiles){
            free(old_quantile);
            old_quantile = NULL;
        }
        self->quantile = new_quantile;
    }
    return 0;
}

static PyObject *
cMultimetrics_repr(cMultimetrics *self){
    static PyObject *format = NULL;
    PyObject *args, *repr;

    char *qstring;  // quantile string
    char *tmp = "";
    for (Py_ssize_t i = 0; i < self->quantile_size; i++) {
        if (i)
            tmp = qstring;
        if (asprintf(&qstring, "%s%s%d",
                     tmp, i?", ":"", self->quantile[i]) == -1){
            return NULL;
        }
        if (i)
            free(tmp);
    }


    format = PyString_FromString("<%s({'timings_is': '%s', "
                                 "'rps': %s, "
                                 "'get_prc': %s, "
                                 "'factor': %s, "
                                 "'quantile': [%s]})>");
    args = Py_BuildValue("ssssis", self->ob_type->tp_name,
                         self->timings_is,
                         self->rps ? "True": "False",
                         self->get_prc ? "True": "False",
                         self->factor,
                         qstring);
    repr = PyString_Format(format, args);
    free(qstring);
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
