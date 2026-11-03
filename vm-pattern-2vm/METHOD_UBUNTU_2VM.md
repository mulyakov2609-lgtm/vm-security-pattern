# Методичка: две Ubuntu-ВМ в VirtualBox

## 0. Итоговая схема и цель текущего этапа
ВМ1 — тестовый источник обращений (атакующая по модели угроз).
ВМ2 — защищаемое приложение и все пять микросервисов в Kubernetes: gateway, api, data, security, audit.

Текущая цель: получить реальный снимок пяти готовых подов в Lens на ВМ2. Функциональные испытания можно выполнить позже. Контейнеры не называются виртуальными машинами: две ВМ созданы VirtualBox, пять подов работают внутри ВМ2.

Используйте ТОЛЬКО новый комплект vm-pattern-2vm. Образ vm-pattern:3.0. Старые внешние адреса data, PROTECTED_APP_URL, run-data.sh и ВМ3 в этой схеме отсутствуют. Исходники и k8s.yaml должны быть из одного нового комплекта.

Методичка рассчитана на физический ПК Intel/AMD, гостевые Ubuntu Desktop 24.04 LTS amd64. При uname -m, отличном от x86_64, бинарник amd64 не подходит. Windows PowerShell, WSL и Docker Desktop не используются. Внутри ВМ2 устанавливается Docker Engine, minikube работает с Docker-драйвером. Нужна работающая виртуализация VirtualBox на основном ПК, но создавать дополнительную аппаратную ВМ внутри Ubuntu не требуется.

## 1. Если предыдущий стенд уже частично установлен
Ничего не удаляйте автоматически. Сохраните нужные журналы и файлы. ВМ3 больше не используется: выключите её и не выделяйте ей ресурсы.
Если используете прежнюю Ubuntu как ВМ2, измените именно её lab-интерфейс на новый адрес 192.168.50.20. Отключите ненужный адаптер lab-back в выключенной ВМ и после проверки сетевых профилей уберите устаревшие адреса. Не удаляйте NAT-профиль.
Если был запущен standalone-контейнер protected-data, он больше не нужен. Проверьте docker ps -a. После сохранения нужного вывода при необходимости выполните docker stop protected-data и docker rm protected-data. Эти команды удаляют старый контейнер и его локальные журналы; не выполняйте их, если такого контейнера нет или он относится к другой работе.
Новый учебный кластер использует профиль vm-lab. Если там старый проект, инструкции обновят Deployment с теми же именами, включая возвращённый data. Проверьте отсутствие чужих политик в secure-app. Не используйте чужой или производственный кластер.

## 2. Создать виртуальные машины
Скачайте ISO Ubuntu Desktop 24.04 LTS amd64 с официального сайта Ubuntu. В VirtualBox создайте две ВМ с отдельными динамическими VDI. При ручной установке можно выбрать Skip Unattended Installation.

Стартовое распределение ресурсов:
- VM1-Client: 2–3 ГБ RAM, 1–2 CPU, диск 25 ГБ.
- VM2-Protected: 6 ГБ RAM, 2 CPU, диск 45 ГБ.
Это предложение для небольшого учебного стенда, не гарантия производительности. На ПК с 16 ГБ закройте остальные ВМ и тяжёлые приложения.

Загрузитесь с ISO, выберите Install Ubuntu, установите систему только на созданный виртуальный диск, задайте имя пользователя и пароль. После установки перезагрузите ВМ и извлеките ISO. Запишите пользователей, не используйте одинаковый виртуальный диск сразу в двух ВМ.
Для Lens на ВМ2 нужен графический рабочий стол. Ubuntu Server допустима для ВМ1, но графические шаги настройки сети ниже предполагают Desktop.

## 3. Настроить адаптеры VirtualBox
Полностью выключите обе ВМ. Для каждой:
- Адаптер 1: NAT, без проброса портов (Интернет для установки).
- Адаптер 2: Внутренняя сеть, точное имя lab-net.
- Кабель подключён на обоих адаптерах.

Не выбирайте сетевой мост. Shared Folders не добавляйте, Shared Clipboard и Drag-and-Drop отключите. Наш Python-код эти настройки автоматически не проверяет и не меняет.
Две ВМ находятся в одной лабораторной сети — это позволяет проверять обращения одной ВМ к другой. Отдельной backend-сети больше нет. Одинаковые адреса NAT вроде 10.0.2.15 у двух ВМ не используются для их взаимного общения.

## 4. Настроить адреса Ubuntu
Терминал Ubuntu: Ctrl+Alt+T. Вставить команду: Ctrl+Shift+V. Пароль sudo при вводе не отображается.

На обеих ВМ:
```bash
ip -br link
ip -br address
nmcli device status
```
Определите интерфейс адаптера 2 по MAC-адресу, сравнив с VirtualBox → Сеть → Дополнительно. Часто это enp0s8, но может отличаться. В командах ниже ЗАМЕНИТЕ enp0s8 на фактическое имя. Не назначайте lab-адрес NAT-интерфейсу.

На ВМ1:
```bash
sudo nmcli connection add type ethernet ifname enp0s8 con-name lab-net ipv4.method manual ipv4.addresses 192.168.50.10/24 ipv4.never-default yes ipv6.method disabled connection.autoconnect-priority 100
sudo nmcli connection up lab-net
```
На ВМ2:
```bash
sudo nmcli connection add type ethernet ifname enp0s8 con-name lab-net ipv4.method manual ipv4.addresses 192.168.50.20/24 ipv4.never-default yes ipv6.method disabled connection.autoconnect-priority 100
sudo nmcli connection up lab-net
```
Создание профиля выполняется один раз. Для уже существующего lab-net используйте nmcli connection modify, а не создавайте дубликаты. Профили смотрятся через nmcli connection show. NAT остаётся DHCP с маршрутом по умолчанию. Для lab-net шлюз и DNS не задаются.

Проверка на ВМ1:
```bash
ping -c 3 192.168.50.20
```
На ВМ2:
```bash
ping -c 3 192.168.50.10
ip -br address
ip route
```
Если ping не проходит, сначала разберите имена сетей, адаптеры, адреса и имеющиеся firewall-правила. Не устанавливайте Kubernetes, пока базовая сеть не готова.

## 5. Базовые пакеты
На обеих ВМ:
```bash
sudo apt update
sudo apt install -y ca-certificates curl openssl unzip nano
```
На ВМ1 больше ничего для текущего снимка устанавливать не нужно. На ВМ2 устанавливаются Docker, minikube и Lens. Windows-хост эти команды не изменяют.

## 6. Установить Docker Engine на ВМ2
Официальная инструкция: https://docs.docker.com/engine/install/ubuntu/.
Команды ниже рассчитаны на новую Ubuntu без конфликтующих установок Docker. Если уже установлен рабочий docker-ce, повторная установка не требуется: проверьте docker info. Если установлен docker.io или podman-docker из другого источника, сначала прочтите раздел конфликтующих пакетов официальной инструкции, не удаляйте рабочие контейнеры вслепую.

На ВМ2:
```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo usermod -aG docker "$USER"
```
Полностью выйдите из учётной записи Ubuntu и войдите снова либо перезагрузите ВМ. Затем:
```bash
id
docker info
```
Docker должен работать от обычного пользователя. Членство в группе docker предоставляет фактически административные права гостевой ОС: не выдавайте его недоверенным пользователям. Не запускайте minikube от root и не обходите проверку флагом --force.
Docker Desktop и WSL здесь не нужны. Docker Compose запускать не требуется.

## 7. Распаковать НОВЫЙ проект на ВМ2
Через браузер ВМ2 скачайте приложенный архив и извлеките папку в домашний каталог. Пример рабочего пути:
```text
/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/vm-pattern-2vm
```
В нём должны быть app.py, Dockerfile, k8s.yaml, setup-token.sh, deploy.sh, start-access.sh и unit_tests.py. Скрытый .dockerignore не всегда виден в менеджере файлов — Ctrl+H включает показ скрытых.

На ВМ2:
```bash
cd ~/vm-pattern-2vm
pwd
ls -la
python3 -m py_compile app.py
bash -n setup-token.sh
bash -n deploy.sh
bash -n start-access.sh
```
Не вставляйте команды в app.py. Импорты и HTTP-обвязка остаются в рабочем коде, даже если в отчёте приводятся только основные функции.

## 8. Установить и запустить minikube на ВМ2
```bash
mkdir -p ~/Downloads/lab-tools
cd ~/Downloads/lab-tools
uname -m
curl -fLO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64
sudo install -m 0755 minikube-linux-amd64 /usr/local/bin/minikube
minikube version
```
Для x86_64 подходит amd64. Если curl сообщает ошибку, не выполняйте install над неполным файлом. Для ARM нужен другой бинарник.

Запуск без sudo:
```bash
minikube start -p vm-lab --driver=docker --cni=calico --cpus=2 --memory=4096
minikube status -p vm-lab
```
Первый запуск требует Интернета и времени для образов. Если не хватает RAM, освободите ресурсы; не продолжайте при неготовом кластере.

Используем подходящий kubectl, предоставляемый minikube:
```bash
alias kubectl='minikube -p vm-lab kubectl --'
kubectl get nodes
kubectl get pods -n kube-system
```
Для новых окон добавьте ОДИН раз:
```bash
echo "alias kubectl='minikube -p vm-lab kubectl --'" >> ~/.bashrc
```
В новом окне при необходимости выполните source ~/.bashrc. Это alias терминала, Lens его не использует. Ожидается узел Ready и готовые системные компоненты.

## 9. Запустить проект на ВМ2
Предусмотрено два равноценных способа: скрипт или команды вручную. Не требуется выполнять оба подряд.

Способ А — скриптом:
```bash
cd ~/vm-pattern-2vm
bash deploy.sh
```
Скрипт создаёт .env, собирает образ vm-pattern:3.0, загружает его в vm-lab, создаёт namespace и Secret, применяет манифест и ожидает готовности пяти Deployment.

Способ Б — те же шаги вручную:
```bash
cd ~/vm-pattern-2vm
bash setup-token.sh
docker build -t vm-pattern:3.0 .
minikube -p vm-lab image load vm-pattern:3.0
kubectl create namespace secure-app --dry-run=client -o yaml | kubectl apply -f -
kubectl -n secure-app create secret generic internal-token --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s.yaml
```
Secret использует ключ INTERNAL_TOKEN, именно он указан в новом k8s.yaml. .env создаётся только на ВМ2 и не копируется на ВМ1. Не показывайте его в снимках.

Ожидание готовности вручную:
```bash
kubectl -n secure-app rollout status deployment/gateway --timeout=180s
kubectl -n secure-app rollout status deployment/api --timeout=180s
kubectl -n secure-app rollout status deployment/data --timeout=180s
kubectl -n secure-app rollout status deployment/security --timeout=180s
kubectl -n secure-app rollout status deployment/audit --timeout=180s
kubectl -n secure-app get pods
```
Ожидаются пять подов с READY=1/1 и STATUS=Running. Имена получают автоматические окончания. Состояние /health не доказывает, что все внутренние обращения и политика защиты уже проверены.

## 10. Если не запускается
```bash
kubectl -n secure-app get pods
kubectl -n secure-app describe pod ИМЯ_ПОДА
kubectl -n secure-app logs deployment/gateway
```
ИМЯ_ПОДА заменяется реальным именем. Особенно важны Events в describe.
- ImagePullBackOff: образ должен называться vm-pattern:3.0 и быть загружен в vm-lab.
- CreateContainerConfigError: проверьте Secret internal-token и ключ INTERNAL_TOKEN.
- CrashLoopBackOff: смотрите журнал соответствующего Deployment.
- Pending: проверьте ресурсы и Events.
- Running 0/1: смотрите readinessProbe и журнал.
Не удаляйте кластер при каждой ошибке. Не отключайте ограничения безопасности вслепую.

Если кластер содержит старый лабораторный проект, новая конфигурация заменяет объекты с теми же именами, но не удаляет посторонние разрешающие NetworkPolicy. Проверьте kubectl -n secure-app get networkpolicy и содержимое подозрительных политик. Любое дополнительное разрешение может изменить смысл изоляции.

## 11. Открыть доступ ВМ1 к gateway
На ВМ2 в отдельном терминале:
```bash
cd ~/vm-pattern-2vm
bash start-access.sh
```
Скрипт выполняет:
```bash
minikube -p vm-lab kubectl -- -n secure-app port-forward --address 127.0.0.1,192.168.50.20 service/gateway 8080:8000
```
Оставьте окно открытым. Адрес должен уже существовать на lab-интерфейсе ВМ2. В отличие от 0.0.0.0, указаны конкретные адреса: локальный и лабораторный, не NAT.

Если UFW уже активен на ВМ2 и блокирует вход, через консоль VirtualBox разрешите только тестовый клиент:
```bash
sudo ufw allow in from 192.168.50.10 to 192.168.50.20 port 8080 proto tcp
```
Не выполняйте ufw enable/reset с неизвестными правилами FORWARD поверх Docker/minikube: это может нарушить сеть кластера. Базовая методичка не обещает полного укрепления firewall узла. Обычная Docker-публикация -p может обходить UFW; в этом проекте хостовый порт 8080 принадлежит kubectl, а не публикации -p. Не заменяйте схему на произвольную публикацию контейнеров.

На ВМ1:
```bash
curl -i --connect-timeout 5 http://192.168.50.20:8080/health
curl -i --connect-timeout 5 http://192.168.50.20:8080/api/data
```
Ожидается 200. Если 429 после нескольких обращений, подождите 11 секунд. Если 503, смотрите готовность api/data и их журналы. Для одного снимка Lens эти функциональные обращения можно отложить.

ВАЖНО: port-forward — временный учебный доступ через Kubernetes API, не production ingress. Он может не сохранять IP ВМ1 в приложении. Поэтому код использует ОБЩИЙ лимит шлюза: 5 запросов за 10 секунд, а не индивидуальный rate limit по IP. X-Forwarded-For от клиента не считается достоверным. Сессия заканчивается при закрытии терминала/переходе пода, после чего её запускают снова. Путь port-forward не является тестом обычных ingress-правил NetworkPolicy.

## 12. Установить Lens и сделать снимок на ВМ2
На ВМ2 Ubuntu Desktop откройте https://lenshq.io/ и загрузите официальный Linux amd64 .deb, если он предлагается. Условия авторизации/лицензирования зависят от текущей версии. Ничего не покупайте вслепую ради снимка. Альтернативный интерфейс возможен, но снимок не должен называться Lens, если используется другая программа.

Установка скачанного пакета:
```bash
cd ~/Downloads
ls -1 *.deb
sudo apt install ./ТОЧНОЕ_ИМЯ_ФАЙЛА.deb
```
Подставьте настоящее имя скачанного файла; используйте Tab. Lens запускается обычным пользователем через меню Ubuntu, не sudo.

Подключите локальный кластер vm-lab. Если не обнаружен, добавьте файл /home/ВАШ_ПОЛЬЗОВАТЕЛЬ/.kube/config через управление Local Kubeconfigs в настройках. Названия пунктов могут отличаться между версиями. kubeconfig содержит данные доступа: не публикуйте его.

В Lens откройте Workloads → Pods, namespace secure-app. Должны быть пять подов gateway, api, data, security, audit с Running и готовностью контейнеров. Имена и возраст отличаются от Абрамова; копировать его названия и DaemonSet не нужно — у нас Deployment, подами управляют ReplicaSet.

Сделайте PNG через средство снимков Ubuntu либо на Windows-хосте Win+Shift+S, выделив окно ВМ. На снимке должны читаться имена, namespace и статусы. Не добавляйте вымышленные CPU/Memory или статусы вручную. Для текущего этапа метрики можно не настраивать.

Подпись: «Рисунок 13 — Поды микросервисов защищаемого приложения в Kubernetes на ВМ2».
Этот снимок заменяет два снимка трёхмашинной версии. Отдельного standalone data больше нет.

## 13. Следующие проверки — пока необязательно
Модульные тесты на ВМ2 (штатный python3 Ubuntu, сторонних пакетов не нужно):
```bash
cd ~/vm-pattern-2vm
python3 -m unittest -v unit_tests
```
Ожидается успешное завершение тестов. Модульный тест не заменяет испытания Docker/Kubernetes.

Файловая политика через шлюз, на ВМ1:
```bash
curl -i -H 'Content-Type: application/json' -d '{"operation":"read","path":"/protected/demo.txt"}' http://192.168.50.20:8080/file-operation
curl -i -H 'Content-Type: application/json' -d '{"operation":"write","path":"/protected/demo.txt"}' http://192.168.50.20:8080/file-operation
```
Ожидаемо 200/403, если окно лимита не исчерпано. Это проверка API, не перехват VirtualBox Shared Folders.

На ВМ2 проверка действительного запрета записи:
```bash
kubectl -n secure-app exec deployment/data -- python -c "open('/protected/probe.txt','w').write('test')"
```
Ожидаемая ошибка Read-only file system здесь означает успешный запрет записи, а не сбой проекта.

Проверка сетевых путей внутри кластера:
```bash
kubectl -n secure-app exec deployment/gateway -- python -c "import socket; socket.create_connection(('data',8000),3)"
kubectl -n secure-app exec deployment/api -- python -c "import socket; s=socket.create_connection(('data',8000),3); print('TCP allowed'); s.close()"
```
Для gateway → data ожидается timeout, для api → data — успешное TCP-соединение. Это отдельная проверка действия Calico/NetworkPolicy, не доказательство защиты всех портов ВМ2.

Журнал:
```bash
kubectl -n secure-app logs deployment/audit --tail=50
```
События хранятся в памяти и stdout, не в долговременной SIEM.

## 14. Сохранить стенд и продолжить позже
Ctrl+C в окне port-forward. На ВМ2:
```bash
minikube stop -p vm-lab
```
После этого выключите Ubuntu штатно. Для продолжения:
```bash
minikube start -p vm-lab
source ~/.bashrc
kubectl -n secure-app get pods
```
Для запросов ВМ1 снова запустите bash start-access.sh. Не выполняйте minikube delete, если хотите сохранить кластер.

После изменения app.py:
```bash
cd ~/vm-pattern-2vm
docker build -t vm-pattern:3.0 .
minikube -p vm-lab image load vm-pattern:3.0 --overwrite=true
kubectl -n secure-app rollout restart deployment
```
После изменения только k8s.yaml: kubectl apply -f k8s.yaml. Если пересоздавали Secret и меняли токен, поды с env должны быть перезапущены; сам файл .env не изменяйте без необходимости.

## 15. Границы реализации
- ВМ1 — клиент, не размещение реального вредоносного ПО. Проверки проводятся только в собственном изолированном стенде.
- HTTP без TLS и единый внутренний токен допустимы только как упрощение учебной реализации.
- Общий лимит gateway одной реплики; состояние теряется при перезапуске.
- audit не является полноценной SIEM/Prometheus/Grafana и не обеспечивает долговременное хранение.
- Запрет mount/execute в API не равен перехвату системных вызовов или Drag-and-Drop. Файловая система read-only не запрещает любое исполнение.
- ClusterIP и NetworkPolicy ограничивают заданные пути сервисов, но не являются универсальной защитой всех служб ВМ или гипервизора.
- Running/Ready подтверждают запуск и /health, не эффективность механизмов защиты.
- Комплект подготовлен и модульно проверен; реальное развёртывание VirtualBox/Docker/Kubernetes в среде подготовки не выполнялось. Ожидаемые результаты не являются протоколом проведённых испытаний.

## 16. Официальные инструкции
Docker Engine Ubuntu: https://docs.docker.com/engine/install/ubuntu/
Docker и firewall: https://docs.docker.com/engine/network/packet-filtering-firewalls/
minikube: https://minikube.sigs.k8s.io/docs/start/
port-forward: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_port-forward/
Lens: https://docs.lenshq.io/k8slens/getting-started/
Ссылки помогают установке и не добавляются автоматически в библиографию курсовой.
