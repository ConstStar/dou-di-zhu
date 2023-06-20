import sys
import enum
import json
import socket
import time
import traceback
from tkinter import *
from tkinter import messagebox

import pygame

host = "127.0.0.1"
port = 9999


class PLAY_STATE(enum.Enum):
    WAIT = 0
    MARKING = 1
    PLAYING = 2
    FREE = 3


class Card:
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    SUITS = ['♥', '◆', '♣', '♠']
    POWERS = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
              '2': 20, '小王': 99, '大王': 100}

    def __init__(self, rank, suit):

        if rank not in self.POWERS.keys():
            raise Exception("无效牌【" + rank + "】")

        self.__rank = rank
        self.__suit = suit
        self.__name = suit + rank
        self.__power = self.POWERS[rank]

    # 重载字符串表示方法
    def __str__(self):
        return self.__name

    # 重载运算符实现排序
    def __lt__(self, other):
        if self.__power == other.__power:
            return self.__suit < other.__suit

        return self.__power < other.__power

    def __eq__(self, other):
        return self.__name == other.__name

    def __hash__(self):
        return hash(self.__name)

    def get_rank(self):
        return self.__rank

    def get_power(self):
        return self.__power


# 出牌逻辑类
# 用来获取出牌类型
# 在客户端就做一些出牌逻辑判断
# 直接告诉服务端出牌类型 服务端只判断类型是否正确
# 不仅为了减轻服务器端压力 ‘
# 也考虑到以后可以加一个功能：有多种出牌类型后用户可以手动选择一种
class CardOrder:
    CARD_ORDER_TYPE = enum.Enum('CARD_ORDER_TYPE', ('一张', '一对', '三张', '双三张',
                                                    '三带一', '三带二', '四带一', '四带二', '四带两对',
                                                    '顺子', '连对', '飞机', '飞机带对子', '炸弹', '王炸'))

    @staticmethod
    def make_card_list(card_str_list):
        # 根据输入生成牌列表   判断每张牌是否有花色，分割花色生成牌列表
        card_list = []
        for card_str in card_str_list:
            if len(card_str) == 0:
                continue

            if card_str[0] in Card.SUITS:
                card_list.append(Card(card_str[1:], card_str[0]))
            else:
                card_list.append(Card(card_str, ""))

        return card_list

    @staticmethod
    # 获取出牌类型
    # 返回值为 出牌类型
    # 如果返回值为-1 则出牌不符合规则
    def get_cards_type(card_str_list):

        # 通过卡片字符串列表 生成 卡片对象列表
        cards = CardOrder.make_card_list(card_str_list)

        cards.sort()

        # 判断是否为一张
        if len(cards) == 1:
            return CardOrder.CARD_ORDER_TYPE['一张'].value

        # 统计数量
        card_count_map = {}
        power_list = []
        for item in cards:
            power = item.get_power()
            if power not in card_count_map.keys():
                card_count_map[power] = 0
            card_count_map[power] += 1
        power_list = tuple(card_count_map.keys())

        # 数量列表
        count_list = []
        # 每个数量对应牌的列表
        count_card_map = {}
        for power in card_count_map.keys():
            count = card_count_map[power]
            if count not in count_card_map.keys():
                count_card_map[count] = []
            count_card_map[count].append(power)
        count_list = tuple(count_card_map.keys())

        # 判断是否为一对
        # 1. 计数只有1种
        # 2. 有数量为2个的牌
        # 3. 数量为2个的牌有1种
        if len(count_card_map) == 1 \
                and 2 in count_list \
                and len(count_card_map[2]) == 1:
            return CardOrder.CARD_ORDER_TYPE['一对'].value

        # 判断是否为三张
        # 1. 计数只有1种
        # 2. 有数量为3个的牌
        # 3. 数量为3个的牌有1种
        if len(count_card_map) == 1 \
                and 3 in count_list \
                and len(count_card_map[3]) == 1:
            return CardOrder.CARD_ORDER_TYPE['三张'].value

        # 判断是否为双三张
        # 1. 计数只有1种
        # 2. 有数量为3个的牌
        # 3. 数量为3个的牌有2种
        if len(count_card_map) == 1 \
                and 3 in count_list \
                and len(count_card_map[3]) == 2:
            return CardOrder.CARD_ORDER_TYPE['双三张'].value

        # 判断是否为三带一
        # 1. 计数只有2种
        # 2. 有数量为3个的牌
        # 3. 有数量为1个的牌
        # 4. 数量为3个的牌有1种
        # 5. 数量为1个的牌有1种
        if len(count_card_map) == 2 \
                and 3 in count_list \
                and 1 in count_list \
                and len(count_card_map[3]) == 1 \
                and len(count_card_map[1]) == 1:
            return CardOrder.CARD_ORDER_TYPE['三带一'].value

        # 判断是否为三带二
        # 1. 计数只有2种
        # 2. 有数量为3个的牌
        # 3. 有数量为2个的牌
        # 4. 数量为3个的牌有1种
        # 5. 数量为2个的牌有1种
        if len(count_card_map) == 2 \
                and 3 in count_list \
                and 2 in count_list \
                and len(count_card_map[3]) == 1 \
                and len(count_card_map[2]) == 1:
            return CardOrder.CARD_ORDER_TYPE['三带二'].value

        # 判断是否为四带一
        # 1. 计数只有2种
        # 2. 有数量为4个的牌
        # 3. 有数量为1个的牌
        # 4. 数量为4个的牌有1种
        # 5. 数量为1个的牌有1种
        if len(count_card_map) == 2 \
                and 4 in count_list \
                and 1 in count_list \
                and len(count_card_map[4]) == 1 \
                and len(count_card_map[1]) == 1:
            return CardOrder.CARD_ORDER_TYPE['四带一'].value

        # 判断是否为四带二
        # 1. 有数量为4个的牌
        # 2. 数量为4个的牌有1种
        # 3. 其他牌数量为2
        if 4 in count_list \
                and len(count_card_map[4]) == 1 \
                and len(cards) - 4 == 2:
            return CardOrder.CARD_ORDER_TYPE['四带二'].value

        # 判断是否为四带两对
        # 1. 计数只有2种
        # 2. 有数量为4个的牌
        # 3. 有数量为2个的牌
        # 4. 数量为4个的牌有1种
        # 5. 数量为2个的牌有2种
        if len(count_card_map) == 2 \
                and 4 in count_list \
                and 2 in count_list \
                and len(count_card_map[4]) == 1 \
                and len(count_card_map[2]) == 2:
            return CardOrder.CARD_ORDER_TYPE['四带两对'].value

        # 判断是否为顺子
        # 1. 计数只有1种
        # 2. 有数量为1个的牌
        # 5. 数量为1个的牌大于等于5种
        if len(count_card_map) == 1 \
                and 1 in count_list \
                and len(count_card_map[1]) >= 5 \
                and CardOrder.__is_continuous(count_card_map[1]):
            return CardOrder.CARD_ORDER_TYPE['顺子'].value

        # 判断是否为连对
        # 1. 计数只有1种
        # 2. 有数量为2个的牌
        # 3. 数量为2个的牌大于等于3种
        # 4. 数量为2个的牌连续
        if len(count_card_map) == 1 \
                and 2 in count_list \
                and len(count_card_map[2]) >= 3 \
                and CardOrder.__is_continuous(count_card_map[2]):
            return CardOrder.CARD_ORDER_TYPE['连对'].value

        # 判断是否为飞机
        # 1. 有数量为3个的牌
        # 2. 数量为3个的牌大于等于2
        # 3. 牌数为3的牌种类数量 等于 其他牌数量
        # 4. 数量为3个的牌连续
        if 3 in count_list \
                and len(count_card_map[3]) >= 2 \
                and len(count_card_map[3]) == len(cards) - len(count_card_map[3]) * 3 \
                and CardOrder.__is_continuous(count_card_map[3]):
            return CardOrder.CARD_ORDER_TYPE['飞机'].value

        # 特判特别的飞机（比如三个飞机带三个相同的牌）
        # 1. 有数量为3个的牌
        # 2. 数量为3个的牌大于等于3
        # 3. 牌数为3的牌种类数量-1 等于 其他牌数量+3
        # 4. 数量为3个的牌连续 有【牌数为3的牌种类数量-1】个连续的
        if 3 in count_list \
                and len(count_card_map[3]) >= 3 \
                and len(count_card_map[3]) - 1 == len(cards) - len(count_card_map[3]) * 3 + 3:
            return CardOrder.CARD_ORDER_TYPE['飞机'].value

        # 判断是否为飞机带对子
        # 1. 计数只有2种
        # 2. 有数量为3个的牌
        # 3. 有数量为2个的牌
        # 4. 数量为3个的牌大于等于2
        # 5. 牌数为2的牌种类数量 等于 牌数为3的牌种类数量
        # 6. 数量为3个的牌连续
        if len(count_card_map) == 2 \
                and 3 in count_list \
                and 2 in count_list \
                and len(count_card_map[3]) >= 2 \
                and len(count_card_map[2]) == len(count_card_map[3]) \
                and CardOrder.__is_continuous(count_card_map[3]):
            return CardOrder.CARD_ORDER_TYPE['飞机带对子'].value

        #  特判特别的飞机带对子（比如两个飞机带四个相同的牌）
        # 1. 有数量为3个的牌
        # 2. 只能有牌为3张、2张、4张的（所以只判断没有数量为1的牌）
        # 3. 数量为3个的牌大于等于2
        # 4. 除【数量为3个的牌】其他牌数量/2 等于 牌数为3的牌种类数量
        # 5. 数量为3个的牌连续
        if 3 in count_list \
                and 1 not in count_list \
                and len(count_card_map[3]) >= 2 \
                and (len(cards) - len(count_card_map[3]) * 3) / 2 == len(count_card_map[3]) \
                and CardOrder.__is_continuous(count_card_map[3]):
            return CardOrder.CARD_ORDER_TYPE['飞机带对子'].value

        # 判断是否为炸弹
        # 1. 计数只有1种
        # 2. 有数量为4个的牌
        # 3. 数量为4个的牌有1种
        if len(count_card_map) == 1 \
                and 4 in count_list \
                and len(count_card_map[4]) == 1:
            return CardOrder.CARD_ORDER_TYPE['炸弹'].value

        # 判断为王炸
        # 1. 计数只有1种
        # 2. 有数量为1个的牌
        # 3. 数量为1个的牌有2种
        # 4. 大王在其中
        # 5. 小王在其中
        if len(count_card_map) == 1 \
                and 1 in count_list \
                and len(count_card_map[1]) == 2 \
                and Card('大王', '').get_power() in count_card_map[1] \
                and Card('小王', '').get_power() in count_card_map[1]:
            return CardOrder.CARD_ORDER_TYPE['王炸'].value

        return -1

    # 判断数组是否连续
    @staticmethod
    def __is_continuous(arr):
        arr.sort()
        for i in range(1, len(arr)):
            if arr[i] != arr[i - 1] + 1:
                return False
        return True


class MyGame:

    def __init__(self, player_name, room_name):
        global host
        global port
        self.__player_name = player_name
        self.__room_name = room_name

        self.screen_size = (1000, 750)

        # 顶端消息
        self.top_message_pos = [100, 180]

        # 卡片设置值
        self.card_image_size = (120, 165)
        self.card_image_pos = [100, 530]
        self.card_offset_x = 30  # 每个牌的间隔
        self.card_offset_y = -20  # 选中牌的偏移量

        # 上一个出牌
        self.last_card_image_pos = [100, 315]
        self.last_card_image_size = (70, 100)
        self.last_card_offset_x = 20  # 每个牌的间隔

        # 底牌
        self.remain_card_image_pos = [100, 30]
        self.remain_card_image_size = (70, 100)
        self.remain_card_offset_x = 40  # 每个牌的间隔

        # 加载卡片图片资源
        self.card_image_map = {}
        for rank in Card.RANKS:
            for suit in Card.SUITS:
                self.card_image_map[suit + rank] = pygame.image.load(f"resources/cards/{suit}{rank}.png")
        self.card_image_map['小王'] = pygame.image.load(f"resources/cards/小王.png")
        self.card_image_map['大王'] = pygame.image.load(f"resources/cards/大王.png")

        # 创建 socket 对象
        self.__clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__clientsocket.connect((host, port))
        self.__clientsocket.send((self.__room_name + "\n" + self.__player_name).encode("utf-8"))
        self.__clientsocket.setblocking(False)

    def play(self):

        try:
            pygame.init()
            screen = pygame.display.set_mode(self.screen_size)
            # 设置窗口标题
            pygame.display.set_caption('国庆斗地主【房间名称:' + self.__room_name + '】')

            font_name = pygame.font.Font('resources/fonts/simhei.ttf', 20)
            font_tip = pygame.font.Font('resources/fonts/simhei.ttf', 20)
            font_top_message = pygame.font.Font('resources/fonts/simhei.ttf', 35)
            font_last_top_message = pygame.font.Font('resources/fonts/simhei.ttf', 20)
            font_my_info = pygame.font.Font('resources/fonts/simhei.ttf', 20)
            font_button = pygame.font.Font('resources/fonts/simhei.ttf', 20)

            my_index = 0  # 我的玩家下标
            my_card_list = []  # 我的卡片列表
            top_message = ''  # 顶端消息
            last_top_message = ''  # 上一次的顶端消息（为了实现显示两次消息内容）
            state = PLAY_STATE.WAIT  # 我的当前状态

            name_list = ['', '', '']  # 玩家名称列表
            card_count_list = [0, 0, 0]  # 卡片计数列表

            last_card_player_index = 0  # 上一个出牌玩家下标
            last_card_type = ''  # 上一个出牌类型
            last_card_list = []  # 上一个出牌的卡片列表

            remain_card_list = []  # 底牌列表

            my_card_choose_map = {}  # 牌的选中状态

            last_data = ''  # 当消息接受一半的时候先保存起来
            while True:

                time.sleep(0.02)

                # 接收Socket消息
                datas = ''
                try:
                    datas = str(self.__clientsocket.recv(1024).decode("utf-8")).split("\n")
                except BlockingIOError as e:
                    pass  # 如果没有数据了

                for data in datas:
                    if data == '':
                        continue

                    if data[-1] != '}':
                        last_data += data
                        continue
                    data = last_data + data
                    last_data = ''

                    data = json.loads(data)
                    print(str(data))
                    if data['code'] == 0:

                        # 这里的更新逻辑就是
                        # 服务器传来那些字段 客户端就更新那些字段

                        obj = data['data']
                        if 'my_index' in obj.keys():
                            my_index = obj['my_index']

                        if 'name_list' in obj.keys():
                            name_list = obj['name_list']

                        if 'my_card_list' in obj.keys():
                            my_card_list = obj['my_card_list']

                        if 'top_message' in obj.keys():
                            last_top_message = top_message
                            top_message = obj['top_message']

                        if 'card_count_list' in obj.keys():
                            card_count_list = obj['card_count_list']

                        if 'last_card_player_index' in obj.keys():
                            last_card_player_index = obj['last_card_player_index']

                        if 'last_card_type' in obj.keys():
                            last_card_type = obj['last_card_type']

                        if 'last_card_list' in obj.keys():
                            last_card_list = obj['last_card_list']

                        if 'remain_card_list' in obj.keys():
                            remain_card_list = obj['remain_card_list']

                        if 'state' in obj.keys():
                            state = PLAY_STATE(obj['state'])

                    elif data['code'] == -1:
                        # 重置所有内容
                        my_card_list = []
                        state = PLAY_STATE.WAIT
                        card_count_list = [0, 0, 0]
                        last_card_player_index = 0
                        last_card_type = ''
                        last_card_list = []
                        remain_card_list = []
                        my_card_choose_map.clear()

                    elif data['code'] == 1:
                        messagebox.showinfo("加入房间", data['data'])
                        pygame.quit()
                        # 终止程序
                        # sys.exit()
                        # 关闭Socket
                        self.__clientsocket.close()
                        # 退出游戏
                        return
                    else:
                        print("!" * 30)
                        print("未处理编码!")
                        print(str(data))
                        print("!" * 30)

                # 玩家名称
                if len(name_list) > my_index:
                    my_name_surface = font_my_info.render(name_list[my_index], True, (0, 0, 0))
                else:
                    my_name_surface = font_my_info.render("未找到索引", True, (0, 0, 0))

                if len(name_list) >= 2:
                    right_name_surface = font_name.render(name_list[(my_index + 1) % len(name_list)], True, (0, 0, 0))
                else:
                    right_name_surface = font_name.render("等待玩家加入", True, (0, 0, 0))

                if len(name_list) >= 3:
                    left_name_surface = font_name.render(name_list[(my_index + 2) % len(name_list)], True, (0, 0, 0))
                else:
                    left_name_surface = font_name.render("等待玩家加入", True, (0, 0, 0))

                # 最上方的提示信息
                top_message_surface = font_top_message.render(top_message, True, (255, 97, 0))
                last_top_message_surface = font_last_top_message.render(last_top_message, True, (255, 97, 0))

                # 上一个出牌的玩家名称
                if len(name_list) > last_card_player_index:
                    last_name_surface = font_my_info.render(name_list[last_card_player_index], True, (255, 0, 0))
                else:
                    last_name_surface = font_my_info.render("", True, (255, 0, 0))

                # 上一个出的牌类型
                last_card_type_surface = font_my_info.render(last_card_type, True, (0, 0, 255))

                # 玩家剩余卡片数量
                my_tip_surface = font_my_info.render(f"剩余{card_count_list[my_index]}张", True, (0, 0, 0))

                if len(card_count_list) >= 2:
                    right_tip_surface = font_tip.render(f"剩余{card_count_list[(my_index + 1) % len(card_count_list)]}张", True, (0, 0, 0))
                else:
                    right_tip_surface = font_tip.render("空座", True, (0, 0, 0))

                if len(card_count_list) >= 3:
                    left_tip_surface = font_tip.render(f"剩余{card_count_list[(my_index + 2) % len(card_count_list)]}张", True, (0, 0, 0))
                else:
                    left_tip_surface = font_tip.render("空座", True, (0, 0, 0))

                # 右边的卡片
                right_card_surface = pygame.Surface((80, 80), flags=pygame.HWSURFACE)
                right_card_surface.fill(color='pink')
                right_card_surface.blit(right_tip_surface, (0, (right_card_surface.get_size()[1] - right_tip_surface.get_size()[1]) / 2 - 5))

                # 左边的卡片
                left_card_surface = pygame.Surface((80, 80), flags=pygame.HWSURFACE)
                left_card_surface.fill(color='pink')
                left_card_surface.blit(left_tip_surface, (0, (left_card_surface.get_size()[1] - left_tip_surface.get_size()[1]) / 2 - 5))

                marking = False  # 正在叫分
                card_playing = False  # 正在出牌
                free_deal = False  # 任意牌

                if state == PLAY_STATE.WAIT:
                    marking = False
                    card_playing = False
                    free_deal = False
                elif state == PLAY_STATE.PLAYING:
                    marking = False
                    card_playing = True
                    free_deal = False
                elif state == PLAY_STATE.FREE:
                    marking = False
                    card_playing = True
                    free_deal = True
                elif state == PLAY_STATE.MARKING:
                    marking = True
                    card_playing = False
                    free_deal = False
                else:
                    print(f"未设置的状态类型{state}")

                # 手中每张牌的图片信息列表
                my_card_image_list = []
                for card_str in my_card_list:
                    image_surface = self.card_image_map[card_str].copy()
                    image_surface = pygame.transform.scale(image_surface, self.card_image_size)
                    card = {'image': image_surface, 'name': card_str, }
                    my_card_image_list.append(card)

                # 上一个出牌 每张牌的图片列表
                last_card_image_list = []
                for card_str in last_card_list:
                    image_surface = self.card_image_map[card_str].copy()
                    image_surface = pygame.transform.scale(image_surface, self.last_card_image_size)
                    last_card_image_list.append(image_surface)

                # 底牌 每张牌的图片列表
                remain_card_image_list = []
                for card_str in remain_card_list:
                    image_surface = self.card_image_map[card_str].copy()
                    image_surface = pygame.transform.scale(image_surface, self.remain_card_image_size)
                    remain_card_image_list.append(image_surface)

                # PyGame循环获取事件，监听事件
                for event in pygame.event.get():
                    # 判断用户是否点了关闭按钮
                    if event.type == pygame.QUIT:
                        # 卸载所有模块
                        pygame.quit()
                        # 终止程序
                        # sys.exit()
                        # 关闭Socket
                        self.__clientsocket.close()
                        # 退出游戏
                        return

                    # 鼠标按下
                    if event.type == pygame.MOUSEBUTTONDOWN:

                        # 鼠标对于卡片的相对位置
                        relative_pos = (event.pos[0] - self.card_image_pos[0], event.pos[1] - self.card_image_pos[1])

                        # 处理点击卡片
                        if 0 <= relative_pos[1] <= 165:
                            # 如果点击的为最后一张牌
                            if (len(my_card_image_list) - 1) * self.card_offset_x <= relative_pos[0] <= (
                                    len(my_card_image_list) - 1) * self.card_offset_x + self.card_image_size[0]:
                                card_name = my_card_image_list[-1]['name']
                                if card_name in my_card_choose_map.keys():
                                    my_card_choose_map[card_name] = not my_card_choose_map[card_name]
                                else:
                                    my_card_choose_map[card_name] = True
                            elif 0 <= relative_pos[0] / self.card_offset_x < len(my_card_image_list):
                                card_name = my_card_image_list[int(relative_pos[0] / self.card_offset_x)]['name']
                                if card_name in my_card_choose_map.keys():
                                    my_card_choose_map[card_name] = not my_card_choose_map[card_name]
                                else:
                                    my_card_choose_map[card_name] = True


                        # 如果为已经选择的牌(选中的y轴会不一样）
                        elif self.card_offset_y <= relative_pos[1] <= self.card_image_size[1] + self.card_offset_y:
                            # 如果点击的为最后一张牌
                            if (len(my_card_image_list) - 1) * self.card_offset_x <= relative_pos[0] <= (
                                    len(my_card_image_list) - 1) * self.card_offset_x + self.card_image_size[0]:

                                card_name = my_card_image_list[-1]['name']
                                if card_name in my_card_choose_map.keys() and my_card_choose_map[card_name]:
                                    my_card_choose_map[card_name] = False

                            elif 0 <= relative_pos[0] / self.card_offset_x < len(my_card_image_list):
                                card_name = my_card_image_list[int(relative_pos[0] / self.card_offset_x)]['name']
                                if card_name in my_card_choose_map.keys() and my_card_choose_map[card_name]:
                                    my_card_choose_map[card_name] = False

                        # 处理点击按钮
                        if 460 <= event.pos[1] <= 460 + 35:

                            # 如果正在出牌，则判断出牌按钮
                            if card_playing:

                                # 【不出】按钮
                                if (not free_deal) and 380 <= event.pos[0] <= 380 + 80:
                                    self.__clientsocket.send("pass".encode("utf-8"))

                                # 【出牌】按钮
                                elif 510 <= event.pos[0] <= 510 + 80:
                                    choose_card_name_list = []
                                    # 获取被选中的牌
                                    for card in my_card_image_list:
                                        if card['name'] in my_card_choose_map.keys() and my_card_choose_map[card['name']]:
                                            choose_card_name_list.append(card['name'])

                                    card_type = CardOrder.get_cards_type(choose_card_name_list)
                                    if card_type == -1:
                                        last_top_message = top_message
                                        top_message = "出牌不符合规则"
                                    else:
                                        s = " ".join(choose_card_name_list) + f'{card_type:02}'
                                        self.__clientsocket.send(s.encode("utf-8"))


                            # 如果正在叫分，则判断叫分按钮
                            elif marking:
                                # 【不叫】按钮
                                if 250 <= event.pos[0] <= 250 + 80:
                                    self.__clientsocket.send("0".encode("utf-8"))

                                # 【1分】按钮
                                elif 380 <= event.pos[0] <= 380 + 80:
                                    self.__clientsocket.send("1".encode("utf-8"))

                                # 【2分】按钮
                                elif 510 <= event.pos[0] <= 510 + 80:
                                    self.__clientsocket.send("2".encode("utf-8"))

                                # 【3分】按钮
                                elif 640 <= event.pos[0] <= 640 + 80:
                                    self.__clientsocket.send("3".encode("utf-8"))

                # 画背景
                screen.fill('lightblue')

                # 计算居中显示手中的牌
                self.card_image_pos[0] = (self.screen_size[0] - ((len(my_card_image_list) - 1) * self.card_offset_x + self.card_image_size[0])) / 2

                # 画手中的牌
                for i in range(len(my_card_image_list)):
                    image_surface = my_card_image_list[i]['image']
                    image_name = my_card_image_list[i]['name']
                    if image_name in my_card_choose_map.keys() and my_card_choose_map[image_name]:
                        screen.blit(image_surface, (self.card_image_pos[0] + i * self.card_offset_x, self.card_image_pos[1] + self.card_offset_y))
                    else:
                        screen.blit(image_surface, (self.card_image_pos[0] + i * self.card_offset_x, self.card_image_pos[1]))

                # 计算居中显示顶端消息
                self.top_message_pos[0] = (self.screen_size[0] - top_message_surface.get_size()[0]) / 2

                # 画顶端消息
                screen.blit(top_message_surface, self.top_message_pos)
                screen.blit(last_top_message_surface, (self.top_message_pos[0], self.top_message_pos[1] - 20))

                # 如果为任意牌 就不展示上一个出牌内容了
                if not free_deal and len(last_card_list) != 0:

                    # 计算居中显示上一次出的牌
                    self.last_card_image_pos[0] = \
                        (self.screen_size[0] - ((len(last_card_image_list) - 1) * self.last_card_offset_x + self.last_card_image_size[0])) / 2

                    # 画上一个出牌的玩家名称
                    screen.blit(last_name_surface, (self.last_card_image_pos[0], self.last_card_image_pos[1] - 60))

                    # 画上一个出的牌类型
                    screen.blit(last_card_type_surface, (self.last_card_image_pos[0], self.last_card_image_pos[1] - 30))

                    # 画上一个出的牌
                    for i in range(len(last_card_image_list)):
                        image_surface = last_card_image_list[i]
                        screen.blit(image_surface, (
                            self.last_card_image_pos[0] + i * self.last_card_offset_x, self.last_card_image_pos[1]))

                # 计算居中显示底牌
                self.remain_card_image_pos[0] = \
                    (self.screen_size[0] - ((len(remain_card_image_list) - 1) * self.remain_card_offset_x + self.remain_card_image_size[0])) / 2

                # 画底牌
                for i in range(len(remain_card_image_list)):
                    image_surface = remain_card_image_list[i]
                    screen.blit(image_surface, (self.remain_card_image_pos[0] + i * self.remain_card_offset_x, self.remain_card_image_pos[1]))

                # 画其他玩家的名称
                screen.blit(left_name_surface, (100, 70))
                screen.blit(right_name_surface, (self.screen_size[0] - 100 - right_name_surface.get_size()[0], 70))

                # 画其他玩家的剩余牌数量
                screen.blit(left_card_surface, (100, 100))
                screen.blit(right_card_surface, (self.screen_size[0] - 100 - right_card_surface.get_size()[0], 100))

                # 画我的信息
                screen.blit(my_name_surface, (35, 700))
                screen.blit(my_tip_surface, (850, 700))

                # 画按钮
                if marking:
                    pygame.draw.rect(screen, (255, 128, 0), (250, 460, 80, 35), 0, border_radius=8)
                    screen.blit(font_button.render("不叫", True, (0, 0, 0)), (270, 467))

                    pygame.draw.rect(screen, (255, 128, 0), (380, 460, 80, 35), 0, border_radius=8)
                    screen.blit(font_button.render("1分", True, (0, 0, 0)), (405, 467))

                    pygame.draw.rect(screen, (255, 128, 0), (510, 460, 80, 35), 0, border_radius=8)
                    screen.blit(font_button.render("2分", True, (0, 0, 0)), (535, 467))

                    pygame.draw.rect(screen, (255, 128, 0), (640, 460, 80, 35), 0, border_radius=8)
                    screen.blit(font_button.render("3分", True, (0, 0, 0)), (665, 467))

                if card_playing:
                    # 如果为任意牌 则显示灰色的【不出】按钮
                    if free_deal:
                        pygame.draw.rect(screen, (192, 192, 192), (380, 460, 80, 35), 0, border_radius=8)
                        screen.blit(font_button.render("不出", True, (0, 0, 0)), (400, 467))
                    else:
                        pygame.draw.rect(screen, (255, 128, 0), (380, 460, 80, 35), 0, border_radius=8)
                        screen.blit(font_button.render("不出", True, (0, 0, 0)), (400, 467))

                    pygame.draw.rect(screen, (255, 128, 0), (510, 460, 80, 35), 0, border_radius=8)
                    screen.blit(font_button.render("出牌", True, (0, 0, 0)), (530, 467))

                pygame.display.flip()  # 更新屏幕内容
        finally:
            pygame.quit()
            self.__clientsocket.close()


class Application(Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.createWidget()

    def createWidget(self):
        # 用户名称输入框
        self.label01 = Label(self, text="玩家名称（2~10个字符）")
        self.label01.pack()

        v1 = StringVar()
        self.entry01 = Entry(self, textvariable=v1)
        self.entry01.pack()

        # 房间名称输入框
        self.label02 = Label(self, text="房间名称（2~10个字符）")
        self.label02.pack()

        v2 = StringVar()
        self.entry02 = Entry(self, textvariable=v2)
        self.entry02.pack()

        Button(self, text="加入房间", command=self.join_room).pack()

    def join_room(self):
        player_name = self.entry01.get()
        room_name = self.entry02.get()
        if len(player_name) < 2 or len(player_name) > 10:
            messagebox.showinfo('玩家名称不符合条件', '玩家名称必须为2~10个字符以内')
            return

        if len(room_name) < 2 or len(room_name) > 10:
            messagebox.showinfo('房间名称不符合条件', '房间名称必须为2~10个字符以内')
            return

        try:
            game = MyGame(player_name, room_name)
            game.play()
        except Exception as ex:
            messagebox.showinfo("异常", str(ex))
            log = open('log.txt', 'a+', encoding="utf-8")
            log.write(traceback.format_exc() + "\n\n")
            log.close()


def test():
    try:
        assert CardOrder.get_cards_type(["♥3"]) == CardOrder.CARD_ORDER_TYPE["一张"].value
        assert CardOrder.get_cards_type(["♥3", "♠3"]) == CardOrder.CARD_ORDER_TYPE["一对"].value

        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3"]) == CardOrder.CARD_ORDER_TYPE["三张"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♥4", "♠4", "◆4"]) == CardOrder.CARD_ORDER_TYPE["双三张"].value

        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♥4"]) == CardOrder.CARD_ORDER_TYPE["三带一"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♥4", "♠4"]) == CardOrder.CARD_ORDER_TYPE["三带二"].value

        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3", "♥4"]) == CardOrder.CARD_ORDER_TYPE["四带一"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3", "♥4", "♠4"]) == CardOrder.CARD_ORDER_TYPE["四带二"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3", "♥4", "♠5"]) == CardOrder.CARD_ORDER_TYPE["四带二"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3", "♥4", "♠4", "♠5", "◆5", ]) == CardOrder.CARD_ORDER_TYPE["四带两对"].value
        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3", "♥5", "♠4", "♠5", "◆5"]) == -1

        assert CardOrder.get_cards_type(["♥3", "♥4", "♠5", "♠6", "♠7"]) == CardOrder.CARD_ORDER_TYPE["顺子"].value
        assert CardOrder.get_cards_type(["♥3", "♥4", "♠5", "♥5", "♠3", "♠4"]) == CardOrder.CARD_ORDER_TYPE["连对"].value
        assert CardOrder.get_cards_type(["♥3", "♥4", "♣5", "♥5", "◆3", "♣3"]) == -1

        assert CardOrder.get_cards_type(["♥3", "◆3", "♣3", "♥4", "♠4", "◆4", "♥5", "♠5"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "♠4", "◆4", "♥5", "♠6"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "♠4", "◆4",
                                         "♥5", "♠5", "◆5", "♣5"]) == CardOrder.CARD_ORDER_TYPE["飞机带对子"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "♠4", "◆4",
                                         "♥5", "♠5", "◆6", "♠6"]) == CardOrder.CARD_ORDER_TYPE["飞机带对子"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆6", "♠6"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆6", "♠6",
                                         "♥7", "◆7", "♠7", "♥8"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆7", "♠8"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆6", "♥7", "◆7", "♥8", "◆8"]) == CardOrder.CARD_ORDER_TYPE["飞机带对子"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆6", "♠6",
                                         "♥7", "◆7", "♥8", "◆8"]) == CardOrder.CARD_ORDER_TYPE["飞机"].value
        assert CardOrder.get_cards_type(["♥3", "◆3", "♠3", "♥4", "◆4", "♠4",
                                         "♥5", "◆5", "♠5", "♥6", "◆6", "♠6",
                                         "♥7", "◆7", "♠7", "♣7", "♥8", "◆8", "♠8", "♣8"]) == CardOrder.CARD_ORDER_TYPE["飞机带对子"].value

        assert CardOrder.get_cards_type(["♥3", "♠3", "◆3", "♣3"]) == CardOrder.CARD_ORDER_TYPE["炸弹"].value
        assert CardOrder.get_cards_type(["大王", "小王"]) == CardOrder.CARD_ORDER_TYPE["王炸"].value

        assert len(set([Card("3", "♥"), Card("3", "♠"), Card("3", "♣"), Card("3", "◆")])) == 4

    except Exception as ex:
        print("没有通过测试")
        print(ex.__str__())
        raise ex


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        host = sys.argv[1]

    test()
    root = Tk()
    root.title("加入房间")
    root.geometry("250x130+670+300")
    app = Application(master=root)
    root.mainloop()
