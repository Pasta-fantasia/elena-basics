#!/usr/bin/env bash

local_dir=` pwd `'/local_data'
APP_HOME='/home/elena_basic'

echo Using:
echo    ${local_dir} as working directory

docker run  --name elena_sample \
        --rm \
        -v ${local_dir}:${APP_HOME}/data \
        -p 8888:8888 \
        fransimo/elena_sample

# for test
#docker run --name elena_sample --rm -ti -v /Users/fran/PycharmProjects/elena-sample/local_data:/home/elena_sample/data fransimo/elena_sample /bin/bash
