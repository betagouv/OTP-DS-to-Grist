release: cd front && npm install && npm run build
web: gunicorn --worker-class gevent -w 1 --bind 0.0.0.0:$PORT app:app
