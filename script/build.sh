# . .env.ci;

if [ -z $(docker network ls --filter name=^${DOCKER_INTERNAL_NETWORK}$ --format="{{ .Name }}") ] ; then
     docker network create ${DOCKER_INTERNAL_NETWORK} ;
fi

bash script/stop_all.sh

bash script/start_all.sh
