# Elena Sample Code

1. Create your elena_config.yaml from local_data/elena_config_example
2. Set your ELENA_HOME to the folder you put that elena_config.yaml 


# To create Test API
https://testnet.binance.vision/
https://www.binance.com/en/support/faq/how-to-test-my-functions-on-binance-testnet-ab78f9a1b8824cf0a106b4229c76496d

# Installation for testing

To instal both elena and elana_sample on a standard x system with creating a user and using virtual env

(venv) elena2@localhost:~$ history 

    8  python3 -m venv venv
    9  source ~/venv/bin/activate
   10  echo "source ~/venv/bin/activate" >> .bashrc

   12  git clone git@github.com:Pasta-fantasia/elena.git
   13  cd elena/
   14  git fetch origin
   15  git branch -a
   16  git switch feature/TODOs
   17  git pull
   18  git config pull.rebase false
   20  pip install -e .
   21  cd ..
   22  git clone git@github.com:Pasta-fantasia/elena-sample.git
   23  cd elena-sample/
   24  pip install -e .
   25  cd
   26  echo "export ELENA_HOME=/......./L_working" >> .bashrc

   30  mkdir /......./L_working
   31  elena
   32  cp elena-sample/local_data/elena_config_example.yaml L_working/elena_config.yaml
   37  joe elena_config.yaml 

   33  joe cron.sh
   34  chmod a+x cron.sh 
   35  crontab -e

# Interact with the exchange while testing

check local_data ccxt_direct.py


