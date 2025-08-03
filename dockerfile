FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    git cmake ninja-build gperf ccache dfu-util \
    device-tree-compiler wget python3-pip python3-setuptools python3-wheel \
    python3-dev python3-ply python3-yaml xz-utils curl \
    gcc-arm-none-eabi libncurses-dev \
    && apt-get clean

# Set up Python tooling
RUN pip3 install west

# Set working directory
WORKDIR /opt/ncs

# Copy your SDK (self-vendored or submodule)
COPY . /opt/ncs

# Initialize and update west
RUN west init -l . && west update && west zephyr-export

# Install Python requirements
RUN pip3 install -r zephyr/scripts/requirements.txt

# Set environment variables
ENV ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
ENV GNUARMEMB_TOOLCHAIN_PATH=/usr

ENV ZEPHYR_BASE=/opt/ncs/zephyr
ENV PATH=$PATH:/opt/ncs/zephyr/scripts

# Default command
CMD ["/bin/bash"]
