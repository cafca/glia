#!/bin/bash
git checkout master
git merge dev
git push heroku master
heroku run python manage.py db upgrade --app=glia
git checkout dev
