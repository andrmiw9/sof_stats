version=$(cat /var/lib/jenkins/workspace/sof_stats/version)

docker build \
--build-arg http_proxy="${HTTP_PROXY}" \
-f deploy/dockerfile \
-t sof_stats:"${version}" \
.