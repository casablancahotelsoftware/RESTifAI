cd tools/RESTifAI

curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

npm install -g newman

sudo apt install -y python3 python3-pip python3-venv python3-tk

sudo apt update

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 src/app.py

deactivate
cd ../../