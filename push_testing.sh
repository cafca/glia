#!/bin/bash
echo "Will push Nucleus to origin"
read
cd nucleus &&
git push &&
cd - &&
git push heroku-dev dev:master &&
heroku run python manage.py db upgrade --app=glia-dev
