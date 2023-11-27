# Elena Sample Code

1. Create your elena_config.yaml from local_data/elena_config_example
2. Set your ELENA_HOME to the folder you put that elena_config.yaml 


# To create Test API on Binance
https://testnet.binance.vision/
https://www.binance.com/en/support/faq/how-to-test-my-functions-on-binance-testnet-ab78f9a1b8824cf0a106b4229c76496d

# Installation for testing

To install both elena and elana_sample on a standard x system with creating a user and using virtual env

Assuming you have a dedicated user for elena:

- create a virtual env and add it to your .bashrc
```
cd $HOME
python3 -m venv venv
source ~/venv/bin/activate
echo "source ~/venv/bin/activate" >> .bashrc
```

- clone elena and switch to the dev branch
```
cd $HOME
git clone git@github.com:Pasta-fantasia/elena.git
cd $HOME/elena/
git fetch origin
git branch -a
git switch feature/TODOs
git pull
```

- install elena 
```
cd $HOME/elena/
pip install -e .
```



Edit L_working/elena_config.yaml

- clone and install the sample strategy 
```
cd $HOME
git clone git@github.com:Pasta-fantasia/elena-sample.git
cd elena-sample/
pip install -e .
```

- create the working directory
```
cd $HOME
echo "export ELENA_HOME=$HOME/L_working" >> .bashrc
mkdir $HOME/L_working
elena
cp $HOME/elena-sample/local_data/elena_config_example.yaml $HOME/L_working/elena_config.yaml
```

- configure your cron

Configure your cron (crontab -e) with something like:
```
0 * * * * /home/elena2/elena-sample/cron.sh
```
Make sure the path to cron.sh is right for your installation. Cron expression can't use variables.


# Installation for developing
- On Pycharm clone elena and elena-sample.
- To test the strategy create a virtual env on elena-sample and from the Pycharm terminal (making sure that the venv is active) run
```
pip install -e ../elena
pip install -r requirements.txt
```

# Interact with the exchange while testing

On local_data directory you'll find ccxt_direct.py with some code that may help you to interact with the exchange manually.
You may need to cancel orders or check balances on a notebook. It's not using elena, it's just ccxt.
