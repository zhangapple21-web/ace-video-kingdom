# 共享信息中枢

`research/` 是规划窗口、执行窗口和复盘窗口之间的共享信息面。这里保存
来源、假设、失败证据、收据和可复用机制；它不是 Provider 队列，也不是
交付批准表。

机器可读的边界与交接协议见
[`shared_information_hub.v1.json`](shared_information_hub.v1.json)。每个新管道
项目会在 `episodes/generated/<project_id>/research/` 写入自己的规划/执行
一致性收据，并回链到本目录的契约。记录应保持追加式、带来源或哈希；未知
状态不能写成通过。
