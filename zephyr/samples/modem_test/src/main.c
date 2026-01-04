#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <string.h>
#include <zephyr/drivers/cellular.h>
#include <zephyr/modem/chat.h>
#include <zephyr/pm/device.h>
#include <string.h>
#include <inttypes.h>
#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/socket.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/modem/chat.h>

#include <string.h>
#include <zephyr/device.h>
#include <zephyr/drivers/cellular.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/socket.h>
#include <zephyr/pm/device.h>
#include <zephyr/pm/device_runtime.h>

#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/modem/chat.h>

#include <inttypes.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/pm/device.h>
#include <zephyr/sys/poweroff.h>
#include <zephyr/sys/util.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/conn_mgr_monitor.h>
#include <zephyr/drivers/gnss.h>
#include "C:\Users\NSameh\Desktop\zephyr\ncs-2.7.0\zephyr\samples\modem_test\src\mqtt.h"
#include "FIFO.h"

LOG_MODULE_REGISTER(main);
#define CONFIG_CYSEAL 1
#define CONFIG_DUAL_SIM 1

char pub_topic[80];
char sub_topic[200];
int16_t rssi;
char ICCID[25];
char IMEI[20];


const struct device *modem = DEVICE_DT_GET(DT_ALIAS(modem));

#define UART_DEVICE_NODE DT_NODELABEL(uart2)
const struct device *uart1_dev = DEVICE_DT_GET(UART_DEVICE_NODE);

#define CMD_BUFFER_LEN 64

uint32_t raised_event;
const void *info;
size_t info_len;

char URL_sub[102] =
    "https://beyti.cypod.solutions:5000/device/configurations?IMEI=";
char ota_update_url[65] = "https://beyti.cypod.solutions:5000/remote/update/";
char URL_len[20];
uint16_t URL_len_len;
bool OTAupdate = false;
const struct device *gpio1;
const struct device *gpio_device;
struct device *flash_dev;
 unsigned long clockUnix;
char IMEI[20];
uint8_t simSelect = 0;
extern uint8_t simMode[11];

/* GNSS Configuration */
#define NO_OF_GNSS_FIXES 3
#define LTF 10  /* Live tracking frequency */

static bool self_test_flag = false;
static bool liveTracking = false;
static bool GPS_modem_status = false;
static uint8_t LBSselect = 0;

static K_SEM_DEFINE(gnss_sem, 0, 1);
static K_SEM_DEFINE(sleep_sem, 0, 1);
static K_TIMER_DEFINE(gps_timer_suspend, NULL, NULL);

/* GNSS device - will be initialized if available */
const struct device *gnss_dev = NULL;
#define GNSS_MODEM gnss_dev


static void update_imei_and_topics(void) {
  char buffer[64];

  if (cellular_get_modem_info(modem, CELLULAR_MODEM_INFO_IMEI, buffer,
                              sizeof(buffer))) {
    LOG_ERR("Failed to get IMEI");
    return;
  }

  /* Copy IMEI safely */
  strncpy(IMEI, buffer, sizeof(IMEI) - 1);
  IMEI[sizeof(IMEI) - 1] = '\0';

//   flashSaveIMEI();
  get_mqtt_pub_topic(buffer, pub_topic);

  /* Build sub_topic in one go */
  snprintf(sub_topic, sizeof(sub_topic), "SUB/%s", IMEI);

  LOG_INF("IMEI: %s", IMEI);
  LOG_INF("Pub Topic: %s", pub_topic);
  LOG_INF("Sub Topic: %s", sub_topic);
}

/* Network event management */
static struct net_mgmt_event_callback net_event_cb;
static K_SEM_DEFINE(l4_connected_sem, 0, 1);

static void net_event_handler(struct net_mgmt_event_callback *cb,
                            uint32_t mgmt_event, struct net_if *iface)
{
    if (mgmt_event == NET_EVENT_L4_CONNECTED) {
        const struct device *dev = net_if_get_device(iface);
        const char *dev_name = dev ? dev->name : "unknown";
        
        LOG_INF("NET_EVENT_L4_CONNECTED received from interface: %s", dev_name);
        
        /* Only accept L4_CONNECTED from cellular/PPP interfaces, not loopback or others */
        if (strstr(dev_name, "ppp") != NULL || strstr(dev_name, "cellular") != NULL || 
            strstr(dev_name, "modem") != NULL) {
            LOG_INF("*** NET_EVENT_L4_CONNECTED from cellular modem! ***");
            k_sem_give(&l4_connected_sem);
        } else {
            LOG_INF("Ignoring L4_CONNECTED from non-cellular interface: %s", dev_name);
        }
    } else {
        LOG_DBG("Network event: 0x%08x on interface %p", mgmt_event, (void*)iface);
    }
}


void parseConfig(char *config) {
    printk("Config: %s\n", config);
}

static void write_message_to_queue(const char *msg) {
    LOG_INF("Test message: %s", msg);
}

static void logBatteryVoltage(void) {
    LOG_INF("Battery logging not implemented");
}

static unsigned long gnss_time_to_epoch(const struct gnss_time *time) {
    /* Simple epoch conversion - adjust based on your needs */
    /* This is a simplified version, proper implementation should handle */
    /* leap years, month lengths, etc. */
    unsigned long epoch = 0;
    int year = 2000 + time->century_year;
    
    /* Days since epoch (1970-01-01) */
    int days = (year - 1970) * 365 + (year - 1969) / 4;
    
    /* Add days for months */
    int month_days[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    for (int i = 1; i < time->month; i++) {
        days += month_days[i];
    }
    
    /* Add leap day if needed */
    if (time->month > 2 && (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0))) {
        days++;
    }
    
    days += time->month_day - 1;
    
    epoch = days * 86400UL + time->hour * 3600UL + time->minute * 60UL + 
            (time->millisecond / 1000);
    
    return epoch;
}

static void gnss_dump_nav_data2(char *buf, size_t buf_size,
                                const struct navigation_data *nav,
                                uint8_t sat_cnt, uint32_t hdop) {
    int len = 0;
    
    len += snprintf(buf + len, buf_size - len, 
                   "{\"lat\":%.6f,\"lon\":%.6f,\"alt\":%.1f,",
                   (double)nav->latitude / 1000000.0,
                   (double)nav->longitude / 1000000.0,
                   (double)nav->altitude / 1000.0);
    
    len += snprintf(buf + len, buf_size - len,
                   "\"speed\":%.1f,\"bearing\":%.1f,",
                   (double)nav->speed / 1000.0,
                   (double)nav->bearing / 1000.0);
    
    len += snprintf(buf + len, buf_size - len,
                   "\"sat_cnt\":%d,\"hdop\":%u}",
                   sat_cnt, hdop);
}

static void gnss_data_cb(const struct device *dev,
                         const struct gnss_data *data) {
  static uint8_t fixCounter = 0; /* Counter for the number of fixes */

  if (data->info.fix_status != GNSS_FIX_STATUS_NO_FIX) {
    LOG_INF(
        "\r\n ******** Got a fix! %d *********\r\n",
        fixCounter);

    uint8_t sat_cnt = data->info.satellites_cnt;
    uint32_t hdop_acc = data->info.hdop;
    struct gnss_time utc_sat_data = data->utc;
    uint16_t seconds = utc_sat_data.millisecond / 1000;
    uint16_t millis = utc_sat_data.millisecond % 1000;

    LOG_INF("UTC Time: %02d:%02d:%02d.%03d, Date: %02d/%02d/%04d",
            utc_sat_data.hour, utc_sat_data.minute, seconds, millis,
            utc_sat_data.month_day, utc_sat_data.month,
            2000 + utc_sat_data.century_year);

    unsigned long epoch = gnss_time_to_epoch(&utc_sat_data);
    LOG_INF("Epoch Time: %lu.%03d", epoch, millis);

    clockUnix = epoch;

    char buf[1024];
    gnss_dump_nav_data2(buf, sizeof(buf), &data->nav_data, sat_cnt, hdop_acc);
    LOG_INF("%s\r\n", buf);
    if (self_test_flag) {
      write_message_to_queue("GPS OK");
    }

    fixCounter++; /* Increment the fix counter */

    if (liveTracking || fixCounter >= NO_OF_GNSS_FIXES) {
      if (liveTracking && myFifo.noElements > 10)
        return;
      if (liveTracking && !(fixCounter % 60))
        logBatteryVoltage();
      ST_message_t pos;
      pos.idType = Id_Type_CyTrack;
      pos.msgType = Msg_Type_GPS;
      if (!liveTracking) {
        char fields[100];
        bool peek = peekFromFifo(pos.msg);
        printk("position string length = %d\r\n", strlen(pos.msg));
        if (peek && (strlen(pos.msg) < 200)) {
          return_power_status(fields, sizeof(fields));
          add_fields_to_json(pos.msg, fields);
          trimJsonBraces(buf);
          removeFirstField(buf);
          add_fields_to_json(pos.msg, buf);
          overwriteLastMessage(&pos);

        } else {
          pos.msg[0] = '\0';
          strncpy(pos.msg, buf, sizeof(pos.msg) - 1);
          pos.msg[sizeof(pos.msg) - 1] = '\0'; /* Ensure null termination */

          fifoPush(&pos);
        }
        k_sem_give(&gnss_sem);
      } else {
        if (fixCounter % LTF == 0) {
          strncpy(pos.msg, buf, sizeof(pos.msg) - 1);
          pos.msg[sizeof(pos.msg) - 1] = '\0'; /* Ensure null termination */

          fifoPush(&pos); /* Push the message */
        }
      }
      if (!liveTracking && fixCounter >= NO_OF_GNSS_FIXES) {
        /* Reset counter after action */
        fixCounter = 0;

        if (gpio1) {
          gpio_pin_set(gpio1, 0, 0);
          LOG_INF("Switching off the modem pin!\n");
        }
        if (GNSS_MODEM) {
          pm_device_action_run(GNSS_MODEM, PM_DEVICE_ACTION_SUSPEND);
        }
        k_timer_stop(&gps_timer_suspend);
        LBSselect = 0;

        k_sem_give(&sleep_sem);
        GPS_modem_status = false;
      }
    }
  } else {
    /* Reset counter on no fix */
    fixCounter = 0;
  }
}

/* Register GNSS callback - must be at file scope */
GNSS_DATA_CALLBACK_DEFINE(NULL, gnss_data_cb);

void select_sim(uint8_t mode) {
  printk("Selecting SIM %d\r\n", mode);

  if (mode == 1) {
    strcpy(simMode, "AT+QDSIM=1");
    LOG_INF("Physical SIM 1 %s\r\n", simMode);
  } else if (mode == 0) {
    strcpy(simMode, "AT+QDSIM=0");
    LOG_INF("Physical SIM 0 %s\r\n", simMode);
  }
}

int StartModem(void) {
    select_sim(simSelect);
    LOG_INF("Powering on modem\n");
    pm_device_action_run(modem, PM_DEVICE_ACTION_RESUME);

    /* Find PPP iface for event monitoring */
    struct net_if *ppp_iface = net_if_get_first_by_type(&NET_L2_GET_NAME(PPP));
    if (!ppp_iface) {
        LOG_ERR("PPP iface not found");
        return -1;
    }

    net_if_up(ppp_iface);

    LOG_INF("PPP interface found, waiting for cellular connection...");

    LOG_INF("Waiting for L4 connected\n");

    int ret = net_mgmt_event_wait_on_iface(ppp_iface,
                                        NET_EVENT_L4_CONNECTED, &raised_event,
                                        &info, &info_len, K_SECONDS(120));
    if (ret != 0) {
        LOG_INF("L4 was not connected in time\n");
        return -1;
    } else{
      LOG_ERR("HEREEEEEEE!!!!");
        printk("Raised event = %X\n", raised_event);
        // printk("Raised event = %X\n", raised_event);
        if (raised_event == 0xF1140003) {
            printk("Raised event = CONNECTED\n");
            return 0;
        } else if (raised_event == 0xF1140002) {
            printk("Raised event = DISCONNECTED\n");
            return -1;
        }
    }
    return -1;  // Default return if no event matched
}

extern int modem_cellular_clock(const struct device *dev);
extern int modem_cellular_get_lbs_location(const struct device *dev);
extern int ConnectBroker(void);

bool publish_all_fifo_messages(char *pub_topic) {
  char S[256]; // Buffer to store the message
  int len, ret;
  const int MAX_RETRIES = 3;
  bool publishDone = true;

  while (publishDone) {
    S[0] = '\0';       // Clear the buffer
    len = fifoPull(S); // Pull the next message from the FIFO

    if (len <= 0) {
      LOG_INF("No more messages in the FIFO\n");
      break; // Exit loop if no more messages to publish
    }

    int retry_count = 0;
    bool success = false;

    // Retry publishing the message until max retries
    while (retry_count < MAX_RETRIES) {
      if (publish_message(pub_topic, S) == 0) {
        LOG_INF("Published message: %s to topic: %s\n", S, pub_topic);
        ret = process_mqtt_and_sleep(500);

        if (ret == 0) { // Successful publish
          success = true;
          break;
        }
      } else {
        LOG_INF("Failed to publish message: %s. Retrying...\n", S);
        DisconnectBroker();
        ConnectBroker();
        process_mqtt_and_sleep(500); // Wait before retrying
      }
      retry_count++;
    }

    if (!success) {
      LOG_INF("Failed to publish message: %s after %d retries. Aborting...\n",
              S, MAX_RETRIES);
      publishDone = false;
      return false;
    }
  }

  LOG_INF("Published all data\n");
  return true;
}

void ReportMessages(void *p1, void *p2, void *p3) {
  ARG_UNUSED(p1);
  ARG_UNUSED(p2);
  ARG_UNUSED(p3);
  
  while (1) {
    int ret = StartModem();
    if (ret != 0) {
        LOG_ERR("Failed to start modem, ret = %d", ret);
    }
    LOG_ERR("ENDEDDDDD?\?\?\?!");
    modem_cellular_clock(modem);
    modem_cellular_get_lbs_location(modem);
    ret = ConnectBroker();
    if (ret != 0) {
      LOG_ERR("Failed to connect to broker, ret = %d", ret);
    } else {
      LOG_INF("Connected to broker successfully");
    }
    process_mqtt_and_sleep(500);
    publish_all_fifo_messages(pub_topic);
    DisconnectBroker();
    LOG_INF("Disconnected from broker");

  }
}
K_THREAD_STACK_DEFINE(thread_stack, 1024);
struct k_thread report_thread;
int main(void)
{
    LOG_INF("Starting modem test application...");
    
    /* Initialize FIFO */
    fifoInit();
    LOG_INF("FIFO initialized");
    
    /* Initialize GNSS if available */
    gnss_dev = DEVICE_DT_GET_OR_NULL(DT_ALIAS(gnss));
    if (gnss_dev && device_is_ready(gnss_dev)) {
        LOG_INF("GNSS device found: %s", gnss_dev->name);
        LOG_INF("GNSS callback registered via GNSS_DATA_CALLBACK_DEFINE");
    } else {
        LOG_WRN("GNSS device not found or not ready - GNSS features disabled");
        gnss_dev = NULL;
    }
    
    /* Register network event handler */
    net_mgmt_init_event_callback(&net_event_cb, net_event_handler,
                                NET_EVENT_L4_CONNECTED);
    net_mgmt_add_event_callback(&net_event_cb);
    LOG_INF("Network event handler registered");

    /* Start the modem thread */
    k_thread_create(&report_thread, thread_stack,
                    K_THREAD_STACK_SIZEOF(thread_stack), ReportMessages, NULL,
                    NULL, NULL, 4, 0, K_NO_WAIT);

    /* Wait for L4 connectivity */
    LOG_INF("Waiting for L4 connected");
    if (k_sem_take(&l4_connected_sem, K_SECONDS(120)) == 0) {
        LOG_INF("*** SUCCESS: L4_CONNECTED event received! ***");
        LOG_INF("*** Network connectivity established! ***");
        
        /* Optionally try a simple network test */
        struct net_if *iface = net_if_get_default();
        if (iface && net_if_is_up(iface)) {
            LOG_INF("Network interface is UP and ready");
            
            /* Print IP addresses */
            for (int i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
                struct net_if_addr *addr = &iface->config.ip.ipv4->unicast[i];
                if (addr->is_used && addr->addr_state == NET_ADDR_PREFERRED) {
                    char ip_str[INET_ADDRSTRLEN];
                    net_addr_ntop(AF_INET, &addr->address.in_addr, 
                                 ip_str, sizeof(ip_str));
                    LOG_INF("IPv4 address: %s", ip_str);
                }
            }
        }
    } else {
        LOG_ERR("*** TIMEOUT: L4_CONNECTED event not received within 120s ***");
        LOG_ERR("*** Network connectivity failed! ***");
    }

    /* Keep running for additional testing */
    while (1) {
        k_sleep(K_MSEC(1000));
    }
    
    return 0;
}
