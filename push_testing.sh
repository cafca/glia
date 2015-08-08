#!/bin/bash
cd nucleus &&
git push &&
cd - &&
git push heroku-dev dev:master &&
heroku run python manage.py db upgrade --app=glia-dev
