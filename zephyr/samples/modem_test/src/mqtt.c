#include "mqtt.h"
// #include "BLE.h"
#include <zephyr/pm/device.h>
#include <zephyr/pm/device_runtime.h>

// extern Assigned_Tags my_Tags;
// extern uint8_t ble_interval;
// extern const struct device *gpio_device;
// extern const struct device *gpio1;
// extern const struct device *const sensor;

// extern void select_sim(uint8_t mode);

struct data {
  char *Configuration; // 0
  char *Username;
  char *Password;
  char *ET;
  char *LT;
  char *HT;
  int remote_update; // 6
  const char *TT;
  const char *PT;
  int FR;
  int activate_sending; // Activation Request
  char *id0;            // 11
  char *id1;
  char *id2;
  char *id3;
  char *id4;
  char *id5;
  char *id6;
  char *id7;
  char *id8;
  char *id9;
  int *trig;
  char *acc_sense;
  char *proximity;
  char *sim;
};

static const struct json_obj_descr data_descr[] = {
    JSON_OBJ_DESCR_PRIM(struct data, Configuration, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, Username, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, Password, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, ET, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, LT, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, HT, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, remote_update, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, TT, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, PT, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, FR, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, activate_sending, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, id0, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id1, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id2, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id3, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id4, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id5, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id6, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id7, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id8, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, id9, JSON_TOK_STRING),
    JSON_OBJ_DESCR_PRIM(struct data, trig, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, acc_sense, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, proximity, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct data, sim, JSON_TOK_NUMBER),
};

/* Buffers for MQTT client. */
uint8_t rx_buffer[APP_MQTT_BUFFER_SIZE];
uint8_t tx_buffer[APP_MQTT_BUFFER_SIZE];

/* The mqtt client struct */
struct mqtt_client client_ctx;

/* MQTT Broker details. */
struct sockaddr_storage broker;

struct zsock_pollfd fds[1];
int nfds;

bool connected;

void prepare_fds(struct mqtt_client *client) {
  if (client->transport.type == MQTT_TRANSPORT_NON_SECURE) {
    fds[0].fd = client->transport.tcp.sock;
  }
#if defined(CONFIG_MQTT_LIB_TLS)
  else if (client->transport.type == MQTT_TRANSPORT_SECURE) {
    fds[0].fd = client->transport.tls.sock;
  }
#endif

  fds[0].events = ZSOCK_POLLIN;
  nfds = 1;
}

void clear_fds(void) { nfds = 0; }

int wait(int timeout) {

  int ret = 0;

  if (nfds > 0) {
    ret = zsock_poll(fds, nfds, timeout);
    if (ret < 0) {
      printk("poll error: %d", errno);
    }
  }

  return ret;
}

extern char pub_topic;
int numberBytes = 0;
// extern void parseConfig(char *config);

// extern bool OTAupdate;

// extern int ET;
// extern int Limit_humidity_H;
// extern int Limit_humidity_L;
// extern int Limit_temperature_H;
// extern int Limit_temperature_L;
// extern int Limit_light_H;
// extern int Limit_light_L;
// extern int Proximity_H;
// extern int Proximity_L;
// extern int Firmware_Reset;
// extern int Activation_Request;
// extern int Tilt_Request;
// extern int Tilt_Senstivity;
// extern int Proximity_Alarm;

extern char IMEI[20];
/* Helper function to handle tags */
// void handle_tag(struct data *temp_results, int ret, int bit_pos,
//                 int tag_index) {
//   if (ret & (1 << bit_pos)) {
//     my_Tags.Assigned_Tags_Count = tag_index + 1;
//     strcpy(my_Tags.Tags_Info.Ble_CyTag_Ids[tag_index],
//            (&temp_results->id0)[tag_index]);
//     printk("id%d: %s\r\n", tag_index,
//            my_Tags.Tags_Info.Ble_CyTag_Ids[tag_index]);
//   } else {
//     memset(my_Tags.Tags_Info.Ble_CyTag_Ids[tag_index], 0,
//            sizeof(my_Tags.Tags_Info.Ble_CyTag_Ids[tag_index]));
//   }
// }

extern struct k_timer ble_scan_timer;
/* MQTT Event Handler */
void mqtt_evt_handler(struct mqtt_client *client, struct mqtt_evt *evt) {
  int rc, ret;
  char sub_buffer[1024];
  struct data temp_results;

  switch (evt->type) {
  case MQTT_EVT_CONNACK:
    if (evt->result != 0) {
      printk("MQTT connect failed %d\n", evt->result);
    } else {
      connected = true;
      printk("MQTT client connected!\n");
    }
    break;

  case MQTT_EVT_DISCONNECT:
    printk("MQTT client disconnected %d\n", evt->result);
    connected = false;
    clear_fds();
    break;

  case MQTT_EVT_PUBACK:
  case MQTT_EVT_PUBCOMP:
    if (evt->result != 0) {
      printk("MQTT %s error %d\n",
             evt->type == MQTT_EVT_PUBACK ? "PUBACK" : "PUBCOMP", evt->result);
    }
    break;

  case MQTT_EVT_PINGRESP:
  case MQTT_EVT_UNSUBACK:
    printk("%s acknowledged\n",
           evt->type == MQTT_EVT_PINGRESP ? "PING" : "Unsubscribe");
    break;

  case MQTT_EVT_SUBACK:
    printk("SUBACK\n");
    break;

  case MQTT_EVT_PUBLISH:
    printk("Received SUB message\n");
    rc = mqtt_read_publish_payload(client, sub_buffer, sizeof(sub_buffer));
    printk("Received Payload: %s\n", sub_buffer);

    int numberBytes = strlen(sub_buffer);
    printk("numberBytes = %d\r\n", numberBytes);

    ret = json_obj_parse(sub_buffer, numberBytes, data_descr,
                         ARRAY_SIZE(data_descr), &temp_results);
    if (ret < 0) {
      printk("JSON Parse Error: %d", ret);
      break;
    }

    // if (ret & (1 << 0)) {
    //   printk("config = %s\r\n", temp_results.Configuration);
    //   parseConfig(temp_results.Configuration);
    // }

    // if (ret & (1 << 3)) {
    //   ET = atoi(temp_results.ET);
    // }

    // if (ret & (1 << 4)) {
    //   Limit_light_L = atoi(temp_results.LT);
    //   char *temp = strstr(temp_results.LT, ",");
    // //   Limit_light_H = atoi(temp + 1);
    // }

    // if (ret & (1 << 5)) {
    //   Limit_humidity_L = atoi(temp_results.HT);
    //   char *temp = strstr(temp_results.HT, ",");
    //   Limit_humidity_H = atoi(temp + 1);
    // }

    // if (ret & (1 << 6)) {
    //   OTAupdate = temp_results.remote_update;
    //   printk("\n\n\n\nota flag = %d\n\n\n\n", OTAupdate);
    // }

    // if (ret & (1 << 7)) {
    //   Limit_temperature_L = atoi(temp_results.TT);
    //   char *temp = strstr(temp_results.TT, ",");
    //   Limit_temperature_H = atoi(temp + 1);
    // }

    // if (ret & (1 << 8)) {
    //   Proximity_L = atoi(temp_results.PT);
    //   char *temp = strstr(temp_results.PT, ",");
    //   Proximity_H = atoi(temp + 1);
    // }

    // if (ret & (1 << 9)) {
    //   Firmware_Reset = temp_results.FR;
    // }

    // if (ret & (1 << 10)) {
    //   Activation_Request = temp_results.activate_sending;
    // }

    /* Handle all tags in a loop */
    // if (ret & (1 << 11)) {
    //   if (strcmp(my_Tags.Tags_Info.Ble_CyTag_Ids[0], temp_results.id0) != 0) {
    //     for (int i = 0; i < Number_Of_Tags_Per_CyTrack; i++) {
    //       // printk("Resetting all cytag counts\r\n");
    //       my_Tags.Tags_Info.Skip_Count[i] = 0;
    //     }
    //   }

    //   for (int i = 0; i < 10; i++) {
    //     // printk("ENTER HANDLE TAG\r\n");
    //     handle_tag(&temp_results, ret, 11 + i, i);
    //   }
    // }
    // if (ret & (1 << 21)) {
    //   printk("Tilt Activation: %d\r\n", temp_results.trig);
    //   Tilt_Request = temp_results.trig;
    //   if (ret & (1 << 22)) {
    //     if (temp_results.trig == 0) {
    //       pm_device_action_run(sensor, PM_DEVICE_ACTION_SUSPEND);
    //     } else if ((temp_results.trig == 1) && (temp_results.acc_sense >= 10) &&
    //                (temp_results.acc_sense <= 40)) {
    //       printk("Tilt Sensitivity: %d\r\n", temp_results.acc_sense);
    //       Tilt_Senstivity = temp_results.acc_sense;
    //       pm_device_action_run(sensor, PM_DEVICE_ACTION_RESUME);
    //       acc_trigger(Tilt_Senstivity);
    //     }
    //   }
    // }

    // if (ret & (1 << 23)) {
    //   printk("Proximity Alarm Status: %d\r\n", temp_results.proximity);
    //   Proximity_Alarm = temp_results.proximity;
    // }

    // if (ret & (1 << 24)) {
    //   printk("Sim Status: %d\r\n", temp_results.sim);
    //   if ((int)temp_results.sim == 0) {
    //     printk("Physical SIM 0\n");
    //     select_sim(0);
    //   } else if ((int)temp_results.sim == 1) {
    //     printk("Physical SIM 1\n");
    //     select_sim(1);
    //   }
    //   flashSaveSimConfig();
    // }

    break;

  default:
    break;
  }
}

// extern uint8_t LBS_str[60];

// char *get_mqtt_payload(enum mqtt_qos qos)
// {
//   char payload[100];
//   int i = 0;
//   snprintk(payload, sizeof(payload), "{\"LBS\":%s}", LBS_str);
//   printk("\nString : %s\n", payload);
//   i++;
//   return payload;
// }

extern char *DeviceName;

int get_mqtt_pub_topic(char *IMEI, char *topic) {
  static uint8_t i = 0;
  const char *baseString = "CyTrack-G/";

  if (i == 0) {

    snprintf(topic, strlen(baseString) + 16, "%s%s", baseString, IMEI);
    i++;
    // Return the resulting string
  }
  return 0;
}

char *get_mqtt_sub_topic(char *IMEI) {
  static uint8_t i = 0;
  if (i == 0) {
    strcat(DeviceName, IMEI);
    strcat(DeviceName, "/sub");
    i++;
    // Return the resulting string
  }

  return DeviceName;
}

// int publish(struct mqtt_client *client, enum mqtt_qos qos)
// {
//   struct mqtt_publish_param param;

//   param.message.topic.qos = qos;
//   param.message.topic.topic.utf8 = "CyCollector_V2/869616064626628";
//   param.message.topic.topic.size = strlen(param.message.topic.topic.utf8);
//   param.message.payload.data = get_mqtt_payload(qos);
//   param.message.payload.len = strlen(param.message.payload.data);
//   param.message_id = 123456;
//   // printk("Packet ID in Publish = %d\r\n", param.message_id);
//   param.dup_flag = 0U;
//   param.retain_flag = 1;

//   return mqtt_publish(client, &param);
// }

// int subscribe(struct mqtt_client *client, enum mqtt_qos qos)
// {

//   struct mqtt_topic cmdTopic[1];
//   cmdTopic[0].topic.utf8 = "andrew/nader";
//   cmdTopic[0].topic.size = strlen("andrew/nader");
//   cmdTopic[0].qos = qos;

//   struct mqtt_subscription_list sub_param = {
//       .list = cmdTopic, .list_count = 1, .message_id = 3497};

//   return mqtt_subscribe(client, &sub_param);
// }

// int unsubscribe(struct mqtt_client *client, enum mqtt_qos qos)
// {

//   struct mqtt_topic cmdTopic[1];
//   cmdTopic[0].topic.utf8 = "andrew/nader";
//   cmdTopic[0].topic.size = strlen("andrew/nader");
//   cmdTopic[0].qos = qos;

//   struct mqtt_subscription_list sub_param = {
//       .list = cmdTopic, .list_count = 1, .message_id = 3497};

//   return mqtt_unsubscribe(client, &sub_param);
// }

// #define NEW_HOST "104.218.120.246"
// #define NEW_PORT 1884

// #define BEYTI

// #ifdef BEYTI
// #define HOST "104.218.120.206"
// #define PORT 8883
// #else
// #define HOST "104.218.120.85"
// #define PORT 1882
// #endif

uint8_t host[32] = "192.0.2.1";
uint16_t port = 1884;
uint8_t hostUsername[32] = "cytracker_user";
uint8_t hostPassword[32] = "cytracker_cypod123";

struct mqtt_utf8 broker_username = {0};
struct mqtt_utf8 broker_password = {0};

// struct mqtt_utf8 broker_username = MQTT_UTF8_LITERAL("cytracker_user");
// struct mqtt_utf8 broker_password = MQTT_UTF8_LITERAL("cytracker_cypod123");

void broker_init(void) {
  // Allocate memory for broker_username.utf8
  // struct mqtt_utf8 broker_username;
  broker_username.utf8 =
      malloc(strlen(hostUsername) + 1); // +1 for null terminator
  if (broker_username.utf8 == NULL) {
    free(broker_username.utf8); // Free previously allocated memory
    // Handle memory allocation failure
    return 1;
  }
  strcpy(broker_username.utf8, hostUsername);
  broker_username.size = strlen(hostUsername);

  // Allocate memory for broker_password.utf8
  // struct mqtt_utf8 broker_password;
  broker_password.utf8 =
      malloc(strlen(hostPassword) + 1); // +1 for null terminator
  if (broker_password.utf8 == NULL) {
    // Handle memory allocation failure
    free(broker_username.utf8); // Free previously allocated memory
    return 1;
  }
  strcpy(broker_password.utf8, hostPassword);
  broker_password.size = strlen(hostPassword);
  struct sockaddr_in *broker4 = (struct sockaddr_in *)&broker;

  broker4->sin_family = AF_INET;
  broker4->sin_port = htons(port);
  printk("Host = %s\n", host);
  printk("port = %d\n", port);

  zsock_inet_pton(AF_INET, host, &broker4->sin_addr);
}

void client_init(struct mqtt_client *client) {
  mqtt_client_init(client);

  broker_init();

  /* MQTT client configuration */
  client->broker = &broker;
  client->evt_cb = mqtt_evt_handler;
  client->client_id.utf8 = (uint8_t *)IMEI;
  client->client_id.size = strlen(IMEI);
  client->user_name = &broker_username;
  printk("Broker Username: %s\n", broker_username.utf8);
  client->password = &broker_password;
  printk("Broker Password: %s\n", broker_password.utf8);
  client->protocol_version = MQTT_VERSION_3_1_1;
  client->clean_session = false;

  /* MQTT buffers configuration */
  client->rx_buf = rx_buffer;
  client->rx_buf_size = sizeof(rx_buffer);
  client->tx_buf = tx_buffer;
  client->tx_buf_size = sizeof(tx_buffer);

  /* MQTT transport configuration */
#if defined(CONFIG_MQTT_LIB_TLS)
#if defined(CONFIG_MQTT_LIB_WEBSOCKET)
  client->transport.type = MQTT_TRANSPORT_SECURE_WEBSOCKET;
#else
  client->transport.type = MQTT_TRANSPORT_SECURE;
#endif

  struct mqtt_sec_config *tls_config = &client->transport.tls.config;

  tls_config->peer_verify = TLS_PEER_VERIFY_REQUIRED;
  tls_config->cipher_list = NULL;
  tls_config->sec_tag_list = m_sec_tags;
  tls_config->sec_tag_count = ARRAY_SIZE(m_sec_tags);
#if defined(MBEDTLS_X509_CRT_PARSE_C) || defined(CONFIG_NET_SOCKETS_OFFLOAD)
  tls_config->hostname = TLS_SNI_HOSTNAME;
#else
  tls_config->hostname = NULL;
#endif

#else
#if defined(CONFIG_MQTT_LIB_WEBSOCKET)
  client->transport.type = MQTT_TRANSPORT_NON_SECURE_WEBSOCKET;
#else
  client->transport.type = MQTT_TRANSPORT_NON_SECURE;
#endif
#endif

#if defined(CONFIG_MQTT_LIB_WEBSOCKET)
  client->transport.websocket.config.host = SERVER_ADDR;
  client->transport.websocket.config.url = "/mqtt";
  client->transport.websocket.config.tmp_buf = temp_ws_rx_buf;
  client->transport.websocket.config.tmp_buf_len = sizeof(temp_ws_rx_buf);
  client->transport.websocket.timeout = 5 * MSEC_PER_SEC;
#endif

#if defined(CONFIG_SOCKS)
  mqtt_client_set_proxy(client, &socks5_proxy,
                        socks5_proxy.sa_family == AF_INET
                            ? sizeof(struct sockaddr_in)
                            : sizeof(struct sockaddr_in6));
#endif
}

/* In this routine we block until the connected variable is 1 */
int try_to_connect(struct mqtt_client *client) {
  int rc, i = 0;

  while (i++ < APP_CONNECT_TRIES && !connected) {

    client_init(client);

    rc = mqtt_connect(client);
    if (rc != 0) {
      PRINT_RESULT("mqtt_connect", rc);
      k_sleep(K_MSEC(500));
      continue;
    }

    prepare_fds(client);

    if (wait(APP_CONNECT_TIMEOUT_MS)) {
      mqtt_input(client);
    }

    if (!connected) {
      mqtt_abort(client);
    }
  }

  if (connected) {
    return 0;
  }

  return -EINVAL;
}

int process_mqtt_and_sleep(int timeout) {
  int64_t remaining = timeout;
  int64_t start_time = k_uptime_get();
  int rc;

  while (remaining > 0 && connected) {
    if (wait(remaining)) {
      rc = mqtt_input(&client_ctx);
      if (rc != 0) {
        printk("mqtt_input", rc);
        return rc;
      }
    }

    rc = mqtt_live(&client_ctx);
    if (rc != 0 && rc != -EAGAIN) {
      printk("mqtt_live", rc);
      return rc;
    } else if (rc == 0) {
      rc = mqtt_input(&client_ctx);
      if (rc != 0) {
        printk("mqtt_input", rc);
        return rc;
      }
    }
    remaining = timeout + start_time - k_uptime_get();
  }
  return 0;
}

int ConnectBroker(void) {
  printk("attempting to connect: ");
  int rc = try_to_connect(&client_ctx);
  PRINT_RESULT("try_to_connect", rc);
  return rc;
}

int DisconnectBroker(void) {
  int rc = mqtt_disconnect(&client_ctx);
  PRINT_RESULT("mqtt_disconnect", rc);
  SUCCESS_OR_EXIT(rc);
}

int publish_message(char *topic, char *payload) {
  struct mqtt_publish_param param;

  param.message.topic.qos = MQTT_QOS_1_AT_LEAST_ONCE;
  param.message.topic.topic.utf8 = (uint8_t *)topic;
  param.message.topic.topic.size = strlen(topic);
  param.message.payload.data = (uint8_t *)payload;
  param.message.payload.len = strlen(payload);
  param.message_id = sys_rand32_get();
  param.dup_flag = 0;
  param.retain_flag = 0;

  return mqtt_publish(&client_ctx, &param);
}

int subscribe_topic(char *topic) {
  struct mqtt_topic subscribe_topics[] = {{.topic =
                                               {
                                                   .utf8 = (uint8_t *)topic,
                                                   .size = strlen(topic),
                                               },
                                           .qos = MQTT_QOS_0_AT_MOST_ONCE}};

  struct mqtt_subscription_list sub_list = {.list = subscribe_topics,
                                            .list_count =
                                                ARRAY_SIZE(subscribe_topics),
                                            .message_id = sys_rand32_get()};

  return mqtt_subscribe(&client_ctx, &sub_list);
}

int unsubscribe_topic(char *topic) {
  struct mqtt_topic subscribe_topics[] = {{.topic =
                                               {
                                                   .utf8 = (uint8_t *)topic,
                                                   .size = strlen(topic),
                                               },
                                           .qos = MQTT_QOS_0_AT_MOST_ONCE}};

  struct mqtt_subscription_list sub_list = {.list = subscribe_topics,
                                            .list_count =
                                                ARRAY_SIZE(subscribe_topics),
                                            .message_id = sys_rand32_get()};

  return mqtt_unsubscribe(&client_ctx, &sub_list);
}