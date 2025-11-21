FROM python:3.9-slim

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs && chmod 755 /app/data /app/logs

# 创建非root用户
RUN useradd -m -u 1000 trader && chown -R trader:trader /app
USER trader

# 启动命令
CMD ["python", "live_trading.py"]