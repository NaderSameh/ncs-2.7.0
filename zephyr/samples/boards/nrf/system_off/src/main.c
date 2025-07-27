/*
 * Copyright (c) 2019 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "retained.h"

#include <inttypes.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/rtc.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/pm/device.h>
#include <zephyr/sys/poweroff.h>
#include <zephyr/sys/util.h>
#include <hal/nrf_gpio.h>
#include <zephyr/drivers/sensor.h>
// static const struct gpio_dt_spec sw0 = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);


  const struct device *gpio_device = DEVICE_DT_GET(DT_ALIAS(gpio0));
  const struct device *gpio1 = DEVICE_DT_GET(DT_ALIAS(gpio1));
  	const struct device *const cons = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

	    const struct device *i2c = DEVICE_DT_GET(DT_ALIAS(i2c0));
// PCF8563 I2C address
#define PCF8563_I2C_ADDR 0x51

// Register addresses
#define TIMER_CONTROL_REG 0x0E
#define TIMER_REG 0x0F
#define CONTROL_STATUS_2_REG 0x01

// PCF8563 I2C instance name from the overlay file
#define I2C_DEV DT_LABEL(DT_NODELABEL(i2c0))


// Function to write to an I2C register
int write_register(const struct device *i2c_dev, uint8_t reg_addr, uint8_t value) {
    uint8_t buf[2] = { reg_addr, value };
    return i2c_write(i2c_dev, buf, sizeof(buf), PCF8563_I2C_ADDR);
}

// Function to read from an I2C register
int read_register(const struct device *i2c_dev, uint8_t reg_addr, uint8_t *value) {
    return i2c_write_read(i2c_dev, PCF8563_I2C_ADDR, &reg_addr, 1, value, 1);
}


void gotosleep() {

const struct device *rtc=  DEVICE_DT_GET(DT_ALIAS(timerrtc));

gpio_pin_configure(gpio_device, 5, GPIO_OUTPUT);

  printf("\n%s system off demo\n", CONFIG_BOARD);
  struct rtc_time timeptr;
  rtc_get_time(rtc, &timeptr);
	gpio_pin_set(gpio_device, 5, 1);
  timeptr.tm_sec = 57;

  //     // Write to Timer_control register (0x0E)
  //         uint8_t timer_control = 0x82; // Enable timer, set clock source to 1 Hz
  //   uint8_t timer_value = 0x02;   // Set countdown period to 1 second
  //   uint8_t control_status_2 = 0x00; // Clear any previous status
  // int ret;
  //       ret = read_register(i2c, CONTROL_STATUS_2_REG, &control_status_2);
  //   if (ret != 0) {
  //       printk("Failed to read Control_status_2 register (error %d)\n", ret);
  //       return;
  //   }

  //   control_status_2 |= (1 << 1); // Set TIE (Timer Interrupt Enable)
  //   ret = write_register(i2c, CONTROL_STATUS_2_REG, control_status_2);
  //   if (ret != 0) {
  //       printk("Failed to write Control_status_2 register (error %d)\n", ret);
  //       return;
  //   }

  //    ret = write_register(i2c, TIMER_CONTROL_REG, timer_control);
  //   if (ret != 0) {
  //       printk("Failed to write Timer_control register (error %d)\n", ret);
  //       return;
  //   } else {
  //     printk("write complete 1 \r\n");
  //   }

  //   // Write to Timer register (0x0F)
  //   ret = write_register(i2c, TIMER_REG, timer_value);
  //   if (ret != 0) {
  //       printk("Failed to write Timer register (error %d)\n", ret);
  //       return;
  //   }else {
  //     printk("write complete 2 \r\n");
  //   }



  rtc_set_time(rtc, &timeptr);
  timeptr.tm_min = timeptr.tm_min + 1;


  // MNi_EnableDCDCPower();

  int x = rtc_alarm_set_time(rtc, 0, RTC_ALARM_TIME_MASK_MINUTE, &timeptr);
  printk("setting alarm time +1! %d \r\n", x);

  if (x != 0)
    NVIC_SystemReset();


  //   	int rc = pm_device_action_run(cons, PM_DEVICE_ACTION_SUSPEND);
	// if (rc < 0) {
	// 	printf("Could not suspend console (%d)\n", rc);
	// }


  // k_msleep(1000);
  // nrf_gpio_cfg_input(11, NRF_GPIO_PIN_PULLUP);
  // nrf_gpio_cfg_sense_set(11, NRF_GPIO_PIN_SENSE_LOW);

  
  gpio_pin_configure(gpio_device, 11, GPIO_INPUT | GPIO_PULL_UP);
  gpio_pin_interrupt_configure(gpio_device, 11, GPIO_INT_LEVEL_LOW);
  	gpio_pin_set(gpio_device, 5, 0);
    printk("ENTERING SLEEEP!");
    k_msleep(3000);
  sys_poweroff();
}



int main(void)
{
	// int rc;


    gpio_pin_configure(gpio1, 0, GPIO_OUTPUT);
    gpio_pin_configure(gpio_device, 8, GPIO_OUTPUT);
    gpio_pin_configure(gpio_device, 28, GPIO_OUTPUT);
	gpio_pin_set(gpio1, 0, 0);
      gpio_pin_set(gpio_device, 28, 0);
    gpio_pin_set(gpio_device, 8, 0);
	// gpio_pin_set(gpio_device, 8, 1);
	k_msleep(1000);


      
// gotosleep();

    const struct device *uart0 = DEVICE_DT_GET(DT_ALIAS(modemuart));
    const struct device *uart1 = DEVICE_DT_GET(DT_ALIAS(gnssuart));
    const struct device *spi = DEVICE_DT_GET(DT_ALIAS(spiflash));

    const struct device *adc = DEVICE_DT_GET(DT_ALIAS(adc));
    const struct device *rtc = DEVICE_DT_GET(DT_ALIAS(timerrtc));
    const struct device *modem = DEVICE_DT_GET(DT_ALIAS(modem));
    const struct device *const sensor = DEVICE_DT_GET_ANY(st_lis2dh);
    const struct device *const gnss = DEVICE_DT_GET(DT_ALIAS(gnss));
    const struct device *const flash_dev2 =
    DEVICE_DT_GET(DT_ALIAS(spiflash0));


  if (sensor == NULL) {
    printf("No device found\n");
  }
  if (!device_is_ready(sensor)) {
    printf("Device %s is not ready\n", sensor->name);
  }

  struct sensor_value accel[3];
  int rc = sensor_sample_fetch(sensor);
  if (rc == 0) {
    rc = sensor_channel_get(sensor, SENSOR_CHAN_ACCEL_XYZ, accel);
  }
  printf("x %f , y %f , z %f \r\n", sensor_value_to_double(&accel[0]),
         sensor_value_to_double(&accel[1]), sensor_value_to_double(&accel[2]));

  // Disable the device
  // struct sensor_value odr = {
  //     .val1 = 1,
  // };

  // rc = sensor_attr_set(sensor, SENSOR_CHAN_ACCEL_XYZ,
  //                      SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
    //  const struct device *spi = DEVICE_DT_GET(DT_NODELABEL(spi1));
  pm_device_action_run(sensor, PM_DEVICE_ACTION_SUSPEND);
    //  pm_device_action_run(spi,PM_DEVICE_ACTION_SUSPEND);

  rc= pm_device_action_run(spi, PM_DEVICE_ACTION_SUSPEND);
		if (rc < 0) {
		printk("Could not suspend console (%d)\n", rc);
	}

  rc= pm_device_action_run(i2c, PM_DEVICE_ACTION_SUSPEND);
	  		if (rc < 0) {
		printk("Could not suspend console (%d)\n", rc);
	}
  rc= pm_device_action_run(uart1, PM_DEVICE_ACTION_SUSPEND);
	  		if (rc < 0) {
		printk("Could not suspend console (%d)\n", rc);
	}
  rc= pm_device_action_run(uart0, PM_DEVICE_ACTION_SUSPEND);
	  		if (rc < 0) {
		printk("Could not suspend console (%d)\n", rc);

	}

    gpio_pin_configure(gpio_device, 28, GPIO_OUTPUT);
    gpio_pin_configure(gpio_device, 12, GPIO_OUTPUT);

    // gpio_pin_configure(gpio_device, 4, GPIO_DISCONNECTED);
    // gpio_pin_configure(gpio_device, 5, GPIO_DISCONNECTED);
    // gpio_pin_configure(gpio_device, 7, GPIO_DISCONNECTED);

    // gpio_pin_configure(gpio_device, 11, GPIO_DISCONNECTED);
    // gpio_pin_configure(gpio_device, 17, GPIO_DISCONNECTED);
    // gpio_pin_configure(gpio_device, 3, GPIO_DISCONNECTED);
    // gpio_pin_configure(gpio1, 8, GPIO_INPUT);
    // gpio_pin_configure(gpio1, 15, GPIO_DISCONNECTED);


    // gpio_pin_configure(gpio_device, 13, GPIO_INPUT | GPIO_PULL_UP);
    // gpio_pin_configure(gpio_device, 14, GPIO_INPUT | GPIO_PULL_UP);

// sd_power_dcdc_mode_set(NRF_POWER_DCDC_ENABLE);

	//     gpio_pin_set(gpio_device, 13, 0);
    // gpio_pin_set(gpio_device, 14, 0);
    gpio_pin_set(gpio_device, 28, 0);
    gpio_pin_set(gpio_device, 8, 0);

    // gpio_pin_set(gpio_device, 4, 0);
    // gpio_pin_set(gpio_device, 5, 0);
    // gpio_pin_set(gpio_device, 7, 0);
    // gpio_pin_set(gpio_device, 17, 0);
    // gpio_pin_set(gpio_device, 3, 0);
    // gpio_pin_set(gpio1, 8, 0);
    // gpio_pin_set(gpio1, 15, 0);
    // gpio_pin_set(gpio_device, 11, 0);
    // gpio_pin_set(gpio_device, 12, 0);
    // gpio_pin_set(gpio_device, 13, 1);
    // gpio_pin_set(gpio_device, 14, 1);
    gpio_pin_set(gpio1, 0, 0);


	if (!device_is_ready(cons)) {
		printf("%s: device not ready.\n", cons->name);
		return 0;
	}

	printf("\n%s system off demo\n", CONFIG_BOARD);

	if (IS_ENABLED(CONFIG_APP_RETENTION)) {
		bool retained_ok = retained_validate();

		/* Increment for this boot attempt and update. */
		retained.boots += 1;
		retained_update();

		printf("Retained data: %s\n", retained_ok ? "valid" : "INVALID");
		printf("Boot count: %u\n", retained.boots);
		printf("Off count: %u\n", retained.off_count);
		printf("Active Ticks: %" PRIu64 "\n", retained.uptime_sum);
	} else {
		printf("Retained data not supported\n");
	}

	/* configure sw0 as input, interrupt as level active to allow wake-up */
	// rc = gpio_pin_configure_dt(&sw0, GPIO_INPUT);
	// if (rc < 0) {
	// 	printf("Could not configure sw0 GPIO (%d)\n", rc);
	// 	return 0;
	// }

	// rc = gpio_pin_interrupt_configure_dt(&sw0, GPIO_INT_LEVEL_ACTIVE);
	// if (rc < 0) {
	// 	printf("Could not configure sw0 GPIO interrupt (%d)\n", rc);
	// 	return 0;
	// }

	// printf("Entering system off; press sw0 to restart\n");

	// rc = pm_device_action_run(cons, PM_DEVICE_ACTION_SUSPEND);
	// if (rc < 0) {
	// 	printf("Could not suspend console (%d)\n", rc);
	// }

	// if (IS_ENABLED(CONFIG_APP_RETENTION)) {
	// 	/* Update the retained state */
	// 	retained.off_count += 1;
	// 	retained_update();
	// }

	sys_poweroff();
	// k_msleep(50000);

	return 0;
}
