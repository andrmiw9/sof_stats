saved_image="./sof_stats.tar"
image="sof_stats"

echo "Loading image $saved_image..."
docker load -i $saved_image || { echo "Docker load: not found image $saved_image, current folder: $(pwd), exiting..." && exit; }
echo "Loaded image: $saved_image!"

docker run -d \
-p 7006:7006 \
-p 80:80 \
-p 443:433 \
--dns 8.8.8.8 \
--restart=always \
--name sof_stats \
$image || { echo "Docker run: not found image $image, exiting..." && exit; }

echo "run_from_image.sh ended!"