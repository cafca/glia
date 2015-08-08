#!/bin/bash
echo "Will push Nucleus to origin"
read
cd nucleus &&
git push &&
cd - &&
git checkout master &&
git merge dev &&
git push heroku master &&
heroku run python manage.py db upgrade --app=glia &&
git checkout dev
