del /S /Q ".\sanic_restplus\static"
mkdir ".\sanic_restplus\static"
mkdir ".\node_modules"
npm install
copy /B node_modules\swagger-ui-dist\* ".\sanic_restplus\static\"
copy node_modules\typeface-droid-sans\index.css ".\sanic_restplus\static\droid-sans.css"
mkdir ".\sanic_restplus\static\files"
copy /B node_modules\typeface-droid-sans\files\* ".\sanic_restplus\static\files\"
del /S /Q node_modules

