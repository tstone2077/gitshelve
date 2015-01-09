#!/bin/bash

# Usage:
#    bash SetupPythonEnvironment.sh [PYTHON_EXE_PATH] [ENV_DIR_NAME]
#
# If any additional setup is needed for this environment, it can be done at 
# the end of the script.  See the commented out pip call as an example.
#
# Note: This script will run on any platform that supports bash/uname.  This 
# includes platforms using msysgit (using Git Bash).
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ $1 == '--help' ]; then
    echo "Usage: $0 [python_binary_path] [environment_name]"
fi

PYTHON_BIN=$1
if [ -z "$PYTHON_BIN" ];then
   PYTHON_BIN=$(which python)
fi


#hack, if windows, append exe to python bin
if [ ! -z $(echo $OS | grep -i "mingw") ]; then
    PYTHON_BIN=$PYTHON_BIN.exe
fi
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1| sed -e 's/Python //')

ENV_NAME=$2
if [ -z "$ENV_NAME" ];then
   OS=$(uname -s)
   ARCH=$(uname --machine)
   ENV_NAME=py$PYTHON_VERSION-$ARCH-$OS
fi
echo Creating environment "$ENV_NAME" using $PYTHON_BIN ...
python $SCRIPT_DIR/virtualenv.py -p "$PYTHON_BIN" $SCRIPT_DIR/"$ENV_NAME" || exit $?
if [ ! -z $(echo $OS | grep -i "mingw") ]; then
    INTERMEDIATE_DIR=Scripts
else
    if [ ! -z $(echo $OS | grep -i "Windows") ]; then
        INTERMEDIATE_DIR=Scripts
    else
        INTERMEDIATE_DIR=bin
    fi
fi

. "$SCRIPT_DIR/$ENV_NAME/$INTERMEDIATE_DIR/activate"

#install packages
pip install coverage==3.6 || exit $?
echo Done creating environment "$ENV_NAME" using $PYTHON_BIN ...

