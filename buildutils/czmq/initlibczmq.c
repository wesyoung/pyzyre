#include "Python.h"

static PyMethodDef Methods[] = {
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "libczmq",
        NULL,
        -1,
        Methods,
        NULL,
        NULL,
        NULL,
        NULL
};

PyMODINIT_FUNC
PyInit_libczmq(void)
{
    PyObject *module = PyModule_Create(&moduledef);
    return module;
}

#else // py2

PyMODINIT_FUNC
initlibczmq(void)
{
    (void) Py_InitModule("libczmq", Methods);
}

#endif
