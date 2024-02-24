#!/bin/bash

version=$(cat version)
echo "Got version: ${version}"

docker build \
-f Dockerfile \
-t sof_stats:"${version}" \
.

echo "Built image: sof_stats:${version}"


# стопаем инстанс под тем же номером, если он есть
echo 'stopping previous...'
docker stop sof_stats_0
echo "deleting previous..."
docker rm sof_stats_0

# -P - publish all exposed ports to the host
docker run -d \
--network host \
--restart=always \
--name sof_stats_0 \
-p 172.152.1.2:7006:7006 \
sof_stats:"${version}"

#--build-arg http_proxy="${HTTP_PROXY}" \

echo "build.sh is completed successfully!"