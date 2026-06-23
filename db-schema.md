# Схема базы данных — Digital Library

Построено по `app/models/models.py` (SQLAlchemy ORM, PostgreSQL). 15 таблиц.

## Карта связей

`USERS` и `BOOKS` — центральные сущности, между ними связующие таблицы.
Обозначения: `>──` / `──<` — сторона «многие», `( )` — внешние ключи, `*` — поле без FK (связь на уровне приложения).

```text
                                  USERS (id)
                                      │
      ┌───────────────────────────────┼───────────────────────────────┐
      │ favourites        (user_id, book_id)                           │
      │ reading_history   (user_id, book_id)                           │
      │ reading_progress  (user_id, book_id)                           │
   ──<│ book_ratings      (user_id, book_id)   [uniq user+book]        │>──  BOOKS (id)
      │ book_access       (user_id, book_id)                           │
      │ bookmarks         (book_id ; user_id*)                         │
      │ notes             (book_id ; user_id*)                         │
      └───────────────────────────────┬───────────────────────────────┘
                                      │
      ┌───────────────────────────────┼─────────────────────────────┐
   ──<│ search_history    (user_id)                                  │
      │ friendships       (user_id, friend_id)   [само-связь users]  │
      │ user_achievements (user_id, code)        [uniq user+code]    │
      │ group_members     (user_id, group_id)    [uniq group+user]   │>──  GROUPS (id)
      └──────────────────────────────────────────────────────────────┘

        GROUPS (id) ──< group_book_access (group_id, book_id) >── BOOKS (id)
                         [uniq group+book]
```

## Связи (текстом)

| Дочерняя таблица | → users | → books | → groups | Назначение |
|------------------|:-------:|:-------:|:--------:|------------|
| favourites | user_id | book_id | — | избранные книги |
| reading_history | user_id | book_id | — | история чтения |
| reading_progress | user_id | book_id | — | позиция чтения у пользователя |
| book_ratings | user_id | book_id | — | оценка (1–5), уник. (user, book) |
| book_access | user_id | book_id | — | прямой доступ к книге |
| bookmarks | user_id* | book_id | — | закладки (user_id без FK) |
| notes | user_id* | book_id | — | заметки (user_id без FK) |
| search_history | user_id | — | — | история поиска |
| friendships | user_id, friend_id | — | — | дружба (само-связь users) |
| user_achievements | user_id | — | — | выданные ачивки, уник. (user, code) |
| group_members | user_id | — | group_id | состав группы, уник. (group, user) |
| group_book_access | — | book_id | group_id | доступ группы к книге, уник. (group, book) |

`*` — `user_id` объявлен как `Integer` без `ForeignKey`; связь логическая.

---

## Таблицы и поля

### users
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| role | varchar(20) | | `user` / `moderator` / `admin` |
| username | varchar(64) | UNIQUE | |
| email | varchar(64) | UNIQUE | |
| password_hash | varchar(256) | | sha256 |
| has_read_book_achievement | bool | | легаси-флаг ачивки |
| invite_token | varchar(64) | UNIQUE | UUID для приглашений |

### books
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| is_visible_to_all | bool | | публичная книга |
| title | varchar(255) | | |
| average_rating | float | | средняя оценка |
| author | varchar(255) | | |
| language | varchar(50) | | |
| genre | varchar(100) | | |
| minio_key | varchar(255) | | ключ файла в MinIO |
| cover_key | varchar(255) | | ключ обложки |
| last_position | float | | |
| cfi | varchar(500) | | EPUB-позиция |

### favourites
| Поле | Тип | Ключ |
|------|-----|------|
| id | int | PK |
| user_id | int | FK → users |
| book_id | int | FK → books |

### bookmarks
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| title | varchar(255) | | |
| book_id | int | FK → books | |
| position | float | | |
| cfi | varchar(500) | | |
| user_id | int | — | без FK (логич. → users) |
| is_shared | bool | | видна друзьям |

### notes
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| title | varchar(255) | | |
| book_id | int | FK → books | |
| position | float | | |
| cfi | varchar(500) | | |
| selected_text | text | | выделенный текст |
| comment | text | | |
| user_id | int | — | без FK (логич. → users) |
| is_shared | bool | | видна друзьям |

### reading_history
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| user_id | int | FK → users | |
| book_id | int | FK → books | |
| last_read_at | datetime | | |
| progress | float | | 0..1 |

### reading_progress
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| user_id | int | FK → users | |
| book_id | int | FK → books | |
| cfi | varchar(500) | | |
| last_position | float | | |

### search_history
| Поле | Тип | Ключ |
|------|-----|------|
| id | int | PK |
| user_id | int | FK → users |
| query | text | |
| created_at | datetime | |

### friendships
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| user_id | int | FK → users | инициатор |
| friend_id | int | FK → users | получатель |
| status | varchar(20) | | `pending` / `accepted` |
| created_at | datetime | | |

### book_ratings
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| score | int | | 1..5 |
| user_id | int | FK → users | |
| book_id | int | FK → books | |
| — | — | UNIQUE (user_id, book_id) | одна оценка на книгу |

### book_access
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| book_id | int | FK → books | ON DELETE CASCADE |
| user_id | int | FK → users | ON DELETE CASCADE |

### groups
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| name | varchar(120) | UNIQUE | |
| created_at | datetime | | |
| deny_download_data | bool | | запрет выгрузки данных |
| deny_import_data | bool | | запрет импорта |
| deny_friends | bool | | запрет приглашать в друзья |
| allow_upload_files | bool | | разрешить загрузку книг |
| allow_manage_groups | bool | | разрешить управление группами |
| allow_manage_books_access | bool | | разрешить управление доступом |

### group_members
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| group_id | int | FK → groups | ON DELETE CASCADE |
| user_id | int | FK → users | ON DELETE CASCADE |
| — | — | UNIQUE (group_id, user_id) | |

### group_book_access
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| group_id | int | FK → groups | ON DELETE CASCADE |
| book_id | int | FK → books | ON DELETE CASCADE |
| — | — | UNIQUE (group_id, book_id) | |

### user_achievements
| Поле | Тип | Ключ | Примечание |
|------|-----|------|------------|
| id | int | PK | |
| user_id | int | FK → users | ON DELETE CASCADE |
| code | varchar(64) | | код ачивки из каталога |
| created_at | datetime | | когда выдана |
| — | — | UNIQUE (user_id, code) | выдаётся один раз |

---

## Как определяется доступ к книге

Пользователь видит книгу, если выполнено хотя бы одно:

1. `users.role = 'admin'` — видит всё;
2. `books.is_visible_to_all = true` — книга публичная;
3. есть запись в `book_access` для этого пользователя;
4. пользователь состоит в группе (`group_members`), которой выдан доступ (`group_book_access`).
