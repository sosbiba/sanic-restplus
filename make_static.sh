#!/usr/bin/env bash
set -x
rm -rf ./sanic_restplus/static
mkdir -p ./sanic_restplus/static
mkdir -p ./node_modules
npm install
cp ./node_modules/swagger-ui-dist/{swagger-ui*.{css,js}{,.map},favicon*.png} ./sanic_restplus/static
cp ./node_modules/typeface-droid-sans/index.css ./sanic_restplus/static/droid-sans.css
cp -R ./node_modules/typeface-droid-sans/files ./sanic_restplus/static/
rm -rf ./node_modules
exit 0
