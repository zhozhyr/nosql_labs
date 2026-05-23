# nosql_labs
# EventHub - NoSQL Database Project

[![EventHub](https://github.com/zhozhyr/nosql_labs/actions/workflows/eventhub.yml/badge.svg)](https://github.com/{your_username}/{your_repo}/actions/workflows/eventhub.yml)

`nosql_labs` — это FastAPI-приложение для выполнения лабораторных работ по курсу NoSQL.

Проект запускается в Docker, использует Redis для пользовательских сессий, MongoDB для хранения пользователей и событий, Apache Cassandra для реакций и отзывов. Функциональность приложения расширяется по мере выполнения лабораторных работ.

## Что есть в проекте

- FastAPI-приложение
- Запуск через Docker Compose
- Конфигурация через `.env.local`
- Redis для пользовательских сессий и кэширования
- MongoDB как хранилище пользователей и событий
- MongoDB sharding для `events` и replica set'ы для высокой доступности
- Apache Cassandra для хранения реакций и отзывов
- Swagger UI для ручной проверки API
- Bruno-коллекция для smoke-проверок

## Технологии

- Python
- FastAPI
- Redis
- MongoDB
- Apache Cassandra
- Docker Compose
- Pytest

## Запуск

Перед запуском проверьте настройки в `.env.local`.

Запуск в фоне:

```bash
make run
```

Запуск с логами в текущем терминале:

```bash
make rund
```

Проверка статуса контейнеров:

```bash
make services
```

Остановка:

```bash
make stop
```

После запуска приложение доступно по адресу [http://localhost:8080](http://localhost:8080), Swagger UI — [http://localhost:8080/docs](http://localhost:8080/docs).

## Конфигурация

Проект использует `.env.local` как основной источник конфигурации.

Основные переменные окружения:

- `APP_HOST` — хост приложения
- `APP_PORT` — порт приложения
- `APP_USER_SESSION_TTL` — TTL пользовательской сессии
- `REDIS_HOST` — хост Redis
- `REDIS_PORT` — порт Redis
- `REDIS_PASSWORD` — пароль Redis
- `REDIS_DB` — номер Redis database
- `MONGODB_DATABASE` — имя базы данных MongoDB
- `MONGODB_USER` — пользователь MongoDB
- `MONGODB_PASSWORD` — пароль MongoDB
- `MONGODB_HOST` — хост `mongos` роутера
- `MONGODB_PORT` — порт MongoDB
- `CASSANDRA_HOSTS` — хост Cassandra
- `CASSANDRA_PORT` — порт Cassandra
- `CASSANDRA_USERNAME` — пользователь Cassandra
- `CASSANDRA_PASSWORD` — пароль Cassandra
- `CASSANDRA_KEYSPACE` — keyspace Cassandra
- `CASSANDRA_CONSISTENCY` — уровень консистентности Cassandra

## Текущая функциональность

### `GET /health`

Проверка работоспособности сервиса.

Ответ:

```json
{"status":"ok"}
```

Если клиент присылает cookie `X-Session-Id`, сервис возвращает её обратно в `Set-Cookie`, но не создаёт новую сессию и не продлевает TTL.

### `POST /session`

Endpoint для создания и обновления анонимной пользовательской сессии.

Сессии:

- хранятся в Redis
- используют cookie `X-Session-Id`
- имеют TTL
- сохраняются по ключу `sid:{session_id}`
- содержат поля `created_at` и `updated_at`

Первый запрос создаёт новую сессию и возвращает `201 Created`. Повторный запрос с существующей сессией обновляет TTL и возвращает `200 OK`.

### `POST /users`

Регистрация пользователя с сохранением `password_hash` в MongoDB и созданием новой авторизованной сессии.

### `POST /auth/login`

Аутентификация пользователя по `username` и `password` с привязкой `user_id` к Redis-сессии.

### `POST /auth/logout`

Завершение пользовательской сессии и удаление cookie `X-Session-Id`.

### `POST /events`

Создание события авторизованным пользователем с сохранением документа в коллекции `events`.

### `GET /events`

Просмотр списка событий с фильтрацией по `title`, `id`, `category`, `price_from`, `price_to`, `city`, `date_from`, `date_to`, `user`, а также пагинацией через `limit` и `offset`. Поддерживает `include=reactions` и `include=reviews`.

### `GET /events/{id}`

Подробная карточка мероприятия. Поддерживает `include=reactions` и `include=reviews`.

### `PATCH /events/{id}`

Редактирование `category`, `price` и `location.city` только организатором мероприятия.

### `GET /users`

Поиск организаторов по `name`/`id` с пагинацией.

### `GET /users/{id}`

Публичная карточка организатора без `password_hash`.

### `GET /users/{id}/events`

Список мероприятий конкретного организатора. Поддерживает `include=reactions` и `include=reviews`.

### `POST /events/{event_id}/like` и `POST /events/{event_id}/dislike`

Реакции авторизованного пользователя на мероприятие. Хранятся в Cassandra, агрегированные счётчики кэшируются в Redis по названию мероприятия.

### `POST /events/{event_id}/reviews`

Создание отзыва на мероприятие авторизованным пользователем. Хранится в Cassandra.

### `GET /events/{event_id}/reviews`

Список отзывов на мероприятие с пагинацией.

### `PATCH /events/{event_id}/reviews/{review_id}`

Редактирование отзыва автором.

## Архитектура

Приложение разложено по фичам, чтобы HTTP-слой, логика сессий и работа с хранилищами были отделены друг от друга.

- [app/main.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/main.py) — точка входа и сборка FastAPI-приложения
- [app/health/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/health/router.py) — HTTP-обработчик `GET /health`
- [app/sessions/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/sessions/router.py) — HTTP-обработчик `POST /session`
- [app/sessions/service.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/sessions/service.py) — логика создания, обновления cookie и валидации `sid`
- [app/sessions/store.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/sessions/store.py) — работа с Redis: хранение hash, TTL и обновление метаданных сессии
- [app/sessions/dependencies.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/sessions/dependencies.py) — сборка Redis store для FastAPI dependency injection
- [app/users/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/users/router.py) — регистрация, поиск и карточки организаторов
- [app/auth/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/auth/router.py) — логин и logout
- [app/events/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/events/router.py) — создание и просмотр событий
- [app/reactions/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reactions/router.py) — реакции на мероприятия
- [app/reactions/repository.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reactions/repository.py) — хранение реакций в Cassandra и кэширование в Redis
- [app/reviews/router.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reviews/router.py) — отзывы на мероприятия
- [app/reviews/repository.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reviews/repository.py) — хранение отзывов в Cassandra и кэширование в Redis
- [app/settings.py](/Users/zhozhyr/PycharmProjects/nosql_labs/app/settings.py) — загрузка конфигурации из `.env.local`
- [docker-compose.yml](/Users/zhozhyr/PycharmProjects/nosql_labs/docker-compose.yml) — запуск приложения, Redis, Cassandra, `mongos`, config server и shard replica set'ов
- [scripts/mongo-init.sh](/Users/zhozhyr/PycharmProjects/nosql_labs/scripts/mongo-init.sh) — инициализация MongoDB replica set'ов и включение шардирования `events.created_by`
- [scripts/cassandra-init.sh](/Users/zhozhyr/PycharmProjects/nosql_labs/scripts/cassandra-init.sh) — инициализация схемы Cassandra (keyspace, таблицы, индексы)
- [scripts/cassandra-init.cql](/Users/zhozhyr/PycharmProjects/nosql_labs/scripts/cassandra-init.cql) — CQL-скрипт создания схемы

## Проверка API

### Swagger

Swagger UI доступен по адресу [http://localhost:8080/docs](http://localhost:8080/docs).

### curl

Создание сессии:

```bash
curl -i -c /tmp/nosql.cookies -X POST http://localhost:8080/session
```

Повторный запрос с той же cookie:

```bash
curl -i -b /tmp/nosql.cookies -X POST http://localhost:8080/session
```

Проверка health-check:

```bash
curl -i http://localhost:8080/health
```

### Bruno

В проекте есть Bruno-коллекция в каталоге [tools/bruno/nosql_labs](/Users/zhozhyr/PycharmProjects/nosql_labs/tools/bruno/nosql_labs).

Её можно использовать для smoke-проверки:

- `POST /session`
- `GET /health` с cookie
- `POST /users`
- `POST /auth/login`
- `POST /events`
- `GET /events`
- `POST /events/{event_id}/like`
- `POST /events/{event_id}/dislike`
- `POST /events/{event_id}/reviews`
- `GET /events/{event_id}/reviews`
- `POST /auth/logout`

## Структура проекта

- [app](/Users/zhozhyr/PycharmProjects/nosql_labs/app) — приложение и основная логика
- [app/health](/Users/zhozhyr/PycharmProjects/nosql_labs/app/health) — health-check API
- [app/sessions](/Users/zhozhyr/PycharmProjects/nosql_labs/app/sessions) — сессии и работа с Redis
- [app/reactions](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reactions) — реакции на мероприятия (Cassandra + Redis)
- [app/reviews](/Users/zhozhyr/PycharmProjects/nosql_labs/app/reviews) — отзывы на мероприятия (Cassandra + Redis)
- [scripts](/Users/zhozhyr/PycharmProjects/nosql_labs/scripts) — скрипты инициализации MongoDB и Cassandra
- [tests](/Users/zhozhyr/PycharmProjects/nosql_labs/tests) — тесты
- [tools](/Users/zhozhyr/PycharmProjects/nosql_labs/tools) — вспомогательные артефакты, включая Bruno-коллекцию
- [docker-compose.yml](/Users/zhozhyr/PycharmProjects/nosql_labs/docker-compose.yml) — запуск приложения и инфраструктуры
- [.env.local](/Users/zhozhyr/PycharmProjects/nosql_labs/.env.local) — конфигурация окружения
- [Makefile](/Users/zhozhyr/PycharmProjects/nosql_labs/Makefile) — команды для запуска и остановки проекта

## Назначение репозитория

Этот репозиторий используется как рабочий проект для лабораторных работ по NoSQL. По мере выполнения следующих лабораторных работ функциональность приложения может расширяться, а README и документация будут обновляться вместе с проектом.
