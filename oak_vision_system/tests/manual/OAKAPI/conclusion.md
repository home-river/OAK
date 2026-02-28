从测试结果来看，with上下文退出Device后，设备会有一个5s左右的掉线时间，在此期间无法被枚举到，
也无法被重新启动。

项目解决方法：

1、最简单：在config_managerload_config后手动sleep（5.0s）。
2、修改config_manager架构，尽量少使用with来读取Devicemetadata。