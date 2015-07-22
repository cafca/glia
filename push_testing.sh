#!/bin/bash
git push heroku-dev dev:master
heroku run python manage.py db upgrade --app=glia-dev
