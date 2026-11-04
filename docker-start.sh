# Create initial version of ponymail.yaml (allow for subsequent edits)
# [setup.py would create an unsuitable file]
if [ ! -f server/ponymail.yaml ]
then
    cp server/ponymail.yaml.docker server/ponymail.yaml
fi

echo Starting ElasticSearch
/etc/init.d/elasticsearch start

echo Starting Apache Server
apache2ctl start

echo Wait for ElasticSearch startup to complete
# the elasticsearch script is supposed to only return when startup is complete
# but the process needs a few more seconds...

until curl -sIf http://localhost:9200/ >/dev/null ; do sleep 1; done

# Check if the database has been created
sleep 1 # allow for database to be loaded
if curl -sS http://localhost:9200/_cat/indices?v | grep ponymail
then
    echo The database has already been set up
else
    echo Setting up database for the first time
    ( cd tools; python3 -u setup.py --devel; )
    echo Adding some emails
    for i in test/resources/*ponymail*202*.mbox
    do
        python3 tools/import-mbox.py --source $i
    done
    sleep 1 # allow ES time to index the emails
fi

echo Starting PonyMail API
cd server
python3 -u main.py --testendpoints