#!/bin/bash

# Actualiza e instala Google Chrome
apt-get update && apt-get install -y wget unzip curl

# Instala Google Chrome estable
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb

# Instala Chromedriver automáticamente (usado por webdriver-manager)
pip install -r requirements.txt
