// #ifndef CYMQTT_H
// #define CYMQTT_H

// #include "config.h"
#include <zephyr/net/mqtt.h>
#include <zephyr/net/socket.h>
#include <zephyr/random/random.h>

#include <string.h>
#include <zephyr/data/json.h>

#include "FIFO-test.h" //For Cytags
// #include "PIN_CTRL.h"


#define APP_CONNECT_TIMEOUT_MS 20000
#define APP_SLEEP_MSECS 2000

#define APP_CONNECT_TRIES 5

#define APP_MQTT_BUFFER_SIZE 1024

#define MQTT_CLIENTID "Zephyr"

/* Set the following to 1 to enable the Bluemix topic format */
#define APP_BLUEMIX_TOPIC 0


#define SUCCESS_OR_EXIT(rc)                                                    \
  {                                                                            \
    if (rc != 0) {                                                             \
      return 1;                                                                \
    }                                                                          \
  }
#define SUCCESS_OR_BREAK(rc)                                                   \
  {                                                                            \
    if (rc != 0) {                                                             \
      break;                                                                   \
    }                                                                          \
  }

#define RC_STR(rc) ((rc) == 0 ? "OK" : "ERROR")
#define PRINT_RESULT(func, rc) printk("%s: %d <%s>\n", (func), rc, RC_STR(rc))

int ConnectBroker(void);
int DisconnectBroker(void);

// Wrapper function for mqtt_publish with QoS 0
int publish_message(char *topic, char *payload);

// Wrapper function for mqtt_subscribe with QoS 0
int subscribe_topic(char *topic);

int process_mqtt_and_sleep(int timeout);

int get_mqtt_pub_topic(char *IMEI, char *topic);

// #endif