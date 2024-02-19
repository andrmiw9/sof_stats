FROM python:3.11.7-slim
MAINTAINER ANDREY MARKIN

# часовой пояс
ENV TZ=Europe/Moscow
ENV PYTHON_VERSION 3.11.7
# pyc файлы не генерить - включаем, тк все равно менять код внутри контейнера без перезапуска не получится
ENV PYTHONDONTWRITEBYTECODE 1
# JIC. Display logs and dont wait for buffer to fill. Maybe loguru flushes buffer on its own, idk.
ENV PYTHONUNBUFFERED 1

WORKDIR /opt/sof_stats

# Прокси чтобы не тянуть все пакеты в докер в виде whl пакетов, а установить их из инета.
# Прокси должна быть в переменных окружения (в Jenkins это обычно в сам pipeline прописывается)
#RUN pip config set global.proxy ${HTTP_PROXY}

# скопировать весь проект за исключением .dockerignore
COPY . .

# --no-cache-dir - не сохранять загружаемые библиотеки на локальной машине для использования их в случае повторной загрузки.
# В контейнере, в случае пересборки, они всё равно будут удалены.
#RUN python -m pip install --no-cache-dir -r requirements.txt

# использовать кэш серва, если у него есть нужные пакеты
RUN --mount=type=cache, target=/root/.cache/pip pip install -r requirements.txt
#RUN --mount=type=cache, target=/root/.cache/pip pip install -r requirements.txt --proxy=${HTTP_PROXY}


# add rights to execute files
#RUN chmod +x run_from_jenkins.sh
RUN chmod +x run_sof_stats.py

CMD ["python", "run_vox_message.py"]