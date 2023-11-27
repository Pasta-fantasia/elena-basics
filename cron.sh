#!/bin/bash

source $HOME/venv/bin/activate
export ELENA_HOME=$HOME/L_working

elena > $HOME/last.log 2>$HOME/last_error.log