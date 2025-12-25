#!/bin/sh

# 1. Создаём директорию и проверяем права
mkdir -p /mosquitto/config
if [ ! -w /mosquitto/config ]; then
  echo "ERROR: /mosquitto/config is not writable!"
  exit 1
fi

# 2. Создаём пользователя mosquitto заранее
if ! id -u mosquitto >/dev/null 2>&1; then
  adduser -D -g '' -s /bin/false -H -u 1000 mosquitto
fi

# 3. Создаём mosquitto.conf
cat > /mosquitto/config/mosquitto.conf << EOF
listener 1883
allow_anonymous false
password_file /mosquitto/config/pwfile
EOF

# 4. Создаём пустой pwfile с правильными правами
rm -f /mosquitto/config/pwfile
touch /mosquitto/config/pwfile
chmod 600 /mosquitto/config/pwfile
chown mosquitto:mosquitto /mosquitto/config/pwfile


# 5. Заполняем pwfile через mosquitto_passwd
echo "${GM__MQTT__USERNAME}:${GM__MQTT__PASSWORD}" | \
  su -s /bin/sh -c "mosquitto_passwd -b /mosquitto/config/pwfile ${GM__MQTT__USERNAME} ${GM__MQTT__PASSWORD}" mosquitto

# 6. Повторная проверка файла
if [ ! -s /mosquitto/config/pwfile ]; then
  echo "ERROR: pwfile is empty or not created!"
  ls -la /mosquitto/config/pwfile
  exit 1
fi

# 7. Запускаем mosquitto
exec su -s /bin/sh -c "mosquitto -c /mosquitto/config/mosquitto.conf" mosquitto
