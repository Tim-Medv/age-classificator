

TOKENS: List[str] = [
    "881fe857881fgde857881f",
    "b55v72d71bfv5572d71b557",
    "7829x71287gj82971287829",
    "61x7eff83617ebv5ff83617",
    "c89v9f9rd8c89bc9f9d8c89",
]

GROUP_URLS: List[str] = [
'ege_op', 'umschool_math', 'inform_web_ege',
'rus_web_ege', 'reshuege', 'egeiloveyou',
'over_hear_lovee', 'iloveu_pics'
]

MAX_COMMENTS_PER_AGE = 10000   # лимит записей на возраст
POSTS_COUNT          = 100       # постов за один запрос
COMMENTS_COUNT       = 100       # комментариев за один запрос

DATA_DIR   = Path("dataset")
CSV_PATH   = DATA_DIR / "data.csv"
CSV_FIELDS = ("comment", "age")


#Глобальные структуры + блокировки

age_counts: Dict[str, int] = {}                 # возраст → сколько уже сохранено
user_age_cache: Dict[int, Union[int, str]] = {} # кэш возраста
new_comments_collected = 0                      # общий счётчик

age_lock     = threading.Lock()
cache_lock   = threading.Lock()
counter_lock = threading.Lock()
file_lock    = threading.Lock()
stop_event   = threading.Event()# сигнал «стоп» (используется только для Ctrl‑C)

# Вспомогательные функции

def api_call_with_retry(
    api: vk_api.VkApiMethod,
    method_path: str,
    max_retries: int = 5,
    **kwargs,
):

    for attempt in range(max_retries):
        try:
            method = api
            for part in method_path.split('.'):
                method = getattr(method, part)
            return method(**kwargs)
        except vk_api.exceptions.ApiError as e:
            if e.code == 6:            # слишком много запросов
                time.sleep(0.5)
                continue
            if e.code == 15:           # Access denied / поста нет — пропускаем
                return None
            print(f"[VK-ERROR] code={e.code} msg={e}")
            return None
        except Exception as e:
            print(f"[UNKNOWN-ERROR] {e}")
            return None
    return None


def get_user_age(api: vk_api.VkApiMethod, user_id: int) -> Union[int, str]:
    """Получаем возраст пользователя с кэшированием."""
    with cache_lock:
        if user_id in user_age_cache:
            return user_age_cache[user_id]

    resp = api_call_with_retry(api, 'users.get', user_ids=user_id, fields='bdate')
    if (
        resp and len(resp) > 0
        and 'bdate' in resp[0]
        and len(resp[0]['bdate'].split('.')) == 3
    ):
        try:
            bdate = datetime.strptime(resp[0]['bdate'], '%d.%m.%Y')
            today = datetime.today()
            age: Union[int, str] = today.year - bdate.year - (
                (today.month, today.day) < (bdate.month, bdate.day)
            )
        except Exception:
            age = 'Не указан'
    else:
        age = 'Не указан'

    with cache_lock:
        user_age_cache[user_id] = age
    return age

#CSV: чтение/запись

DATA_DIR.mkdir(exist_ok=True)
CSV_FILE = open(CSV_PATH, 'a', newline='', encoding='utf-8')  # общий файл


def preload_existing_counts() -> None:
    """Загружаем уже собранные возраста из CSV."""
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            age = row['age']
            if age != 'Не указан':
                age_counts[age] = age_counts.get(age, 0) + 1

preload_existing_counts()

print(f"Уже сохранено: {sum(age_counts.values())} комментариев.")
for a in sorted(age_counts, key=int):
    print(f"Возраст {a}: {age_counts[a]}")


def write_row(writer: csv.DictWriter, row: Dict[str, Union[str, int]]) -> None:
    """Потокобезопасная запись в CSV и сброс буфера."""
    with file_lock:
        writer.writerow({'comment': row['comment'], 'age': row['age']})
        CSV_FILE.flush()

#Основные функции

def get_comments(
    api: vk_api.VkApiMethod,
    owner_id: str,
    post_id: int,
    csv_writer: csv.DictWriter,
    group_url: str,
) -> None:
    offset = 0
    while not stop_event.is_set():
        resp = api_call_with_retry(
            api, 'wall.getComments',
            owner_id=owner_id,
            post_id=post_id,
            count=COMMENTS_COUNT,
            offset=offset,
            thread_items_count=10
        )
        if not resp or not resp.get('items'):
            return

        offset += COMMENTS_COUNT

        for comment in resp['items']:
            if stop_event.is_set():
                return

            uid = comment['from_id']
            if uid <= 0:  # комментарий сообщества
                continue

            wc = len(comment['text'].split())
            if wc < 25 or wc > 300:
                continue

            age = get_user_age(api, uid)
            if age == 'Не указан' or not (14 <= int(age) <= 73):
                continue

            age_key = str(age)
            with age_lock:
                age_counts[age_key] = age_counts.get(age_key, 0) + 1

            write_row(csv_writer, {'comment': comment['text'], 'age': age})

            # логируем с timestamp и именем потока
            tname = threading.current_thread().name
            print(f"{datetime.now().isoformat()} [{tname}][{group_url}] "
                  f"добавлен комментарий (возраст {age})")

            with counter_lock:
                global new_comments_collected
                new_comments_collected += 1


def process_posts(
    api: vk_api.VkApiMethod,
    group_id: int,
    csv_writer: csv.DictWriter,
    group_url: str,
) -> None:
    offset = 0
    old_in_a_row = 0

    while not stop_event.is_set():
        resp = api_call_with_retry(
            api, 'wall.get',
            owner_id=f"-{group_id}",
            count=POSTS_COUNT,
            offset=offset
        )
        if not resp or not resp.get('items'):
            return

        offset += POSTS_COUNT

        for post in resp['items']:
            if stop_event.is_set():
                return

            date_post = datetime.fromtimestamp(post['date'])
            if date_post < datetime(2022, 1, 1):
                old_in_a_row += 1
                if old_in_a_row > 3:
                    return
                continue
            old_in_a_row = 0

            get_comments(
                api,
                owner_id=f"-{group_id}",
                post_id=post['id'],
                csv_writer=csv_writer,
                group_url=group_url
            )
            if stop_event.is_set():
                return


def worker(token: str, group_queue: queue.Queue) -> None:
    tname = threading.current_thread().name
    print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] старт потока")

    session = vk_api.VkApi(token=token)
    api     = session.get_api()
    writer  = csv.DictWriter(CSV_FILE, fieldnames=CSV_FIELDS)

    while not stop_event.is_set():
        try:
            group_url = group_queue.get(timeout=1)
        except queue.Empty:
            break

        print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] "
              f"забрал задачу {group_url}")

        resp = api_call_with_retry(api, 'groups.getById', group_ids=group_url)
        if not resp:
            print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] "
                  f"не удалось получить ID {group_url}")
            group_queue.task_done()
            continue

        group_id = resp[0]['id']
        print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] "
              f"обрабатываю {group_url}")

        process_posts(api, group_id, writer, group_url)

        print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] "
              f"завершил {group_url}")
        group_queue.task_done()

    print(f"{datetime.now().isoformat()} [{tname}][{token[:6]}] поток завершает работу")


def main() -> None:
    start = time.time()

    if CSV_PATH.stat().st_size == 0:
        w = csv.DictWriter(CSV_FILE, fieldnames=CSV_FIELDS)
        w.writeheader()
        CSV_FILE.flush()

    group_queue: queue.Queue[str] = queue.Queue()
    for g in GROUP_URLS:
        group_queue.put(g)

    with ThreadPoolExecutor(max_workers=len(TOKENS)) as executor:
        for t in TOKENS:
            executor.submit(worker, t, group_queue)

        # дожидаемся обработки всех групп
        group_queue.join()
        stop_event.set()

    elapsed = round(time.time() - start, 2)
    print(f"\nСобрано новых комментариев: {new_comments_collected} за {elapsed} сек.")
    print("Итоговое распределение по возрастам:")
    for a in sorted(age_counts, key=int):
        print(f"Возраст {a}: {age_counts[a]}")

    CSV_FILE.close()


if __name__ == '__main__':
    main()
