#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON2=$(which python2)
PYTHON3=$(which python3)
VIRTUAL_ENV_DIR=$SCRIPT_DIR/../virtualenv
TEST_ROOT_FILE=$SCRIPT_DIR/t_gitshelve.py

if [ -n "$PYTHON2" ]; then
    #make sure we have a python2 environment
    ls -d $VIRTUAL_ENV_DIR/py2.* > /dev/null 2>&1
    if [ $? != 0 ]; then
        bash $VIRTUAL_ENV_DIR/SetupPythonEnvironment.sh "$PYTHON2" || exit $?
    fi
    PYTHON2_ENV=$(ls -d $VIRTUAL_ENV_DIR/py2.*)
fi

if [ -n "$PYTHON3" ]; then
    #make sure we have a python2 environment
    ls -d $VIRTUAL_ENV_DIR/py3.* > /dev/null 2>&1
    if [ $? != 0 ]; then
        bash $VIRTUAL_ENV_DIR/SetupPythonEnvironment.sh "$PYTHON3" || exit $?
    fi
    PYTHON3_ENV=$(ls -d $VIRTUAL_ENV_DIR/py3.*)
fi

OS=$(uname -s)
if [ ! -z $(echo $OS | grep -i "mingw") ]; then
    INTERMEDIATE_DIR=Scripts
else
    INTERMEDIATE_DIR=bin
fi

if [ -n "$PYTHON2_ENV" ]; then
    echo ======================================
    echo Python 2
    echo --------------------------------------
    . "$PYTHON2_ENV/$INTERMEDIATE_DIR/activate"
    coverage erase
    python --version
    coverage --version
    coverage run --branch --omit=*t_*.py $TEST_ROOT_FILE $@
    echo ======================================
fi

if [ -n "$PYTHON3_ENV" ]; then
    echo ======================================
    echo Python 3
    echo --------------------------------------
    . "$PYTHON3_ENV/$INTERMEDIATE_DIR/activate"
    python --version
    coverage --version
    coverage run --append --branch --omit=*t_*.py $TEST_ROOT_FILE $@
    echo ======================================
fi

if [ -z $1 ]; then
    coverage report -m --omit=*t_*.py
    coverage xml -i -o $SCRIPT_DIR/coverage.xml
fi
