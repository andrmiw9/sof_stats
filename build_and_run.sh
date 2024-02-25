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
#-p 172.152.1.2:7006:7006 \
#-p 192.168.3.100:7006:7006 \
# запустилось без network host
#--network host \ - ломает входящие запросы нафиг и с WSL2 и с винды
# http://172.17.31.170:7006/search?tag=python&smth=foo - работает
# http://127.0.0.1:7006/search?tag=python&smth=foo - работает
# 7006 порт - фаст апи, 80 - http запросы, 443 - https запросы

docker run -d \
-p 7006:7006 \
-p 80:80 \
-p 443:433 \
--dns 8.8.8.8 \
--restart=always \
--name sof_stats_0 \
sof_stats:"${version}"

#--build-arg http_proxy="${HTTP_PROXY}" \

echo "build.sh is completed successfully!"