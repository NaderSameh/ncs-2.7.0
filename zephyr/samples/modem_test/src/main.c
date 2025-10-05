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
#include "D:\ncs-D\v2.7.0-rc3\zephyr\samples\modem_test\src\mqtt.h"

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

  flashSaveIMEI();
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
        }
    }
}

extern int modem_cellular_clock(const struct device *dev);
extern int modem_cellular_get_lbs_location(const struct device *dev);

extern int ConnectBroker(void);
void ReportMessages(void) {
  // k_msgq_get(&my_msgq, &data, K_FOREVER);
  int ret = 0;
  while (1) {
    int ret = StartModem();
    if (ret != 0) {
        LOG_ERR("Failed to start modem, ret = %d", ret);
    }
    LOG_ERR("ENDEDDDDD????!");
    modem_cellular_clock(modem);
    modem_cellular_get_lbs_location(modem);
    ret = ConnectBroker();
    if (ret != 0) {
      LOG_ERR("Failed to connect to broker, ret = %d", ret);
    } else {
      LOG_INF("Connected to broker successfully");
    }

  }
}
K_THREAD_STACK_DEFINE(thread_stack, 1024);
struct k_thread report_thread;
int main(void)
{
    LOG_INF("Starting modem test application...");
    
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
