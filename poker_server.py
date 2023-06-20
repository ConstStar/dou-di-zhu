import json
import random
import enum
import socket
from threading import Thread
import time


class PLAY_STATE(enum.Enum):
    WAIT = 0
    MARKING = 1
    PLAYING = 2
    FREE = 3


# 定义异常类
class MyException(Exception):
    # 异常代码枚举
    EXCEPTION_CODE_TYPE = enum.Enum('EXCEPTION_CODE_TYPE', ('ONE', 'ALL', 'INFO', 'ERROR', 'WARNING'))

    __code = EXCEPTION_CODE_TYPE.INFO
    __message = ''

    def __init__(self, code, message):
        self.__code = code
        self.__message = message

    # 获取异常编码
    def get_code(self):
        return self.__code

    # 获取异常信息
    def get_message(self):
        return self.__message

    # 重载字符串表示方法
    def __str__(self):
        return str(self.__code) + ":\n" + self.__message


# 定义扑克类
class Card:
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    SUITS = ['♥', '◆', '♣', '♠']
    POWERS = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
              '2': 20, '小王': 99, '大王': 100}

    def __init__(self, rank, suit):

        if rank not in self.POWERS.keys():
            raise MyException(MyException.EXCEPTION_CODE_TYPE.WARNING, "无效牌【" + rank + "】")

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


# 定义扑克盒类
class CardBox:

    # 构造方法
    def __init__(self):
        self.__cards = []

    # 生成牌
    def create(self):
        for suit in Card.SUITS:
            for rank in Card.RANKS:
                self.__cards.append(Card(rank, suit))
        self.__cards.append(Card('小王', ''))
        self.__cards.append(Card('大王', ''))
        self.shuffle()

    # 洗牌
    def shuffle(self):
        random.shuffle(self.__cards)

    # 拿一张牌
    def get_card(self):
        if len(self.__cards) == 0:
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ERROR, "程序错误，牌已经发完了")

        top_card = self.__cards[0]
        self.__cards.remove(top_card)
        return top_card

    # 发牌，每人默认发17张牌
    def deal(self, players, per_cards=17):
        for rounds in range(per_cards):
            for player in players:
                card = self.get_card()
                player.add_card(card)

    # 获取剩余牌（获取底牌）
    def get_remain(self):
        result = self.__cards
        self.__cards = []
        return result


# 消息类
class Message:

    def __init__(self, top_message=None,
                 my_index=None, my_card_list=None,
                 name_list=None, card_count_list=None,
                 last_card_player_index=None, last_card_type=None, last_card_list=None,
                 remain_card_list=None,
                 state=None):
        obj = {
            'my_index': my_index, 'name_list': name_list, 'my_card_list': my_card_list,
            'top_message': top_message, 'card_count_list': card_count_list,
            'last_card_player_index': last_card_player_index, 'last_card_type': last_card_type,
            'last_card_list': last_card_list,
            'remain_card_list': remain_card_list,
            'state': None
            }
        if state != None:
            obj['state'] = state.value

        data = {}
        for k, v in obj.items():
            if v != None:
                data[k] = v

        self.__data = data

    def get_data(self):
        return self.__data


# 定义玩家类
class Player:

    # 构造方法
    def __init__(self, name, clientsocket, addr, room):

        self.__name = name
        self.__cards = []
        self.__clientsocket = clientsocket
        self.__addr = addr
        self.__room = room
        self.__th_close = False
        self.__th = Thread(target=self.while_send)
        self.__th.start()

    # 重载字符串表示方法
    def __str__(self):
        rep = ''
        if self.__cards:
            rep = self.__name + ": "
            for card in self.__cards:
                rep += str(card) + " "
        else:
            rep = "无牌"

        return rep

    def get_name(self):
        return self.__name

    # 添加一张牌
    def add_card(self, card):
        self.__cards.append(card)

    # 添加多张牌
    def add_cards(self, cards):
        self.__cards.extend(cards)

    # 整理牌（排序）
    def sort_cards(self):
        self.__cards.sort(reverse=True)

    # 移除多张牌
    def remove_cards(self, cards):
        myCards = self.__cards.copy()
        for card in cards:
            if card not in myCards:
                raise MyException(MyException.EXCEPTION_CODE_TYPE.WARNING, f"你没有足够的【{str(card)}】")
            myCards.remove(card)
        self.__cards = myCards

    def get_cards(self):
        return self.__cards.copy()

    def clear(self):
        self.__cards.clear()

    def send(self, code, data):
        try:
            j = json.dumps({'code': code, 'data': data, 'player': self.__name})
            data = j + "\n"
            self.__clientsocket.send(data.encode("utf-8"))
        except ConnectionError as ex:
            self.close()
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ALL, "【" + self.__name + "】退出房间")

    def receive(self):
        try:
            data = str(self.__clientsocket.recv(1024).decode("utf-8"))
            # print("receive:" + data)
            return data.strip()
        except ConnectionError as ex:
            self.close()
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ALL, "【" + self.__name + "】退出房间")

    def send_message(self, message):
        self.send(0, message.get_data())

    def send_info(self, message):
        self.send(1, message)

    def send_stop_play(self):
        self.send(-1, None)

    # 发送心跳包
    def while_send(self):
        while not self.__th_close:
            self.send_message(Message())
            time.sleep(5)

    def get_card_str_list(self):
        return [str(card) for card in self.__cards]

    def receive_message(self):

        while True:
            msg = self.receive()
            if len(msg.split("\n")) == 1:
                return msg

            self.send_message("格式错误，请重新输入")

    def close(self):
        self.__th_close = True
        self.__room.remove_player(self)
        self.__clientsocket.close()

    def __hash__(self):
        return hash(str(self.__addr) + "\n" + self.__room.get_name() + "\n" + self.__name)

    def __eq__(self, other):
        return self.__addr == other.__addr and self.__name == other.__name and self.__room.get_name() == other.__room.get_name()


class PLAY_STATE(enum.Enum):
    WAIT = 0
    MARKING = 1
    PLAYING = 2
    FREE = 3


# 出牌逻辑类
class CardOrder:
    CARD_ORDER_TYPE = enum.Enum('CARD_ORDER_TYPE', ('一张', '一对', '三张', '双三张',
                                                    '三带一', '三带二', '四带一', '四带二', '四带两对',
                                                    '顺子', '连对', '飞机', '飞机带对子', '炸弹', '王炸'))

    def __init__(self, cards, cards_type):

        if len(cards) == 0:
            raise MyException(MyException.EXCEPTION_CODE_TYPE.WARNING, "出牌为空")

        result, power = self.check_card_type(cards, cards_type)
        if not result:
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ONE, "出牌不符合规则")

        self.__cards = cards
        self.__power = 0
        self.__type = cards_type
        self.__power = power

    # 检查扑克牌类型
    # 返回值为:(result类型是否正确,power权值)
    @staticmethod
    def check_card_type(cards, cards_type):

        result = False
        power = 0

        cards.sort()

        # 统计数量
        card_count_map = {}
        power_list = []
        for item in cards:
            item_power = item.get_power()
            if item_power not in card_count_map.keys():
                card_count_map[item_power] = 0
            card_count_map[item_power] += 1
        power_list = tuple(card_count_map.keys())

        # 数量列表
        count_list = []
        # 每个数量对应牌的列表
        count_card_map = {}
        for item_power in card_count_map.keys():
            count = card_count_map[item_power]
            if count not in count_card_map.keys():
                count_card_map[count] = []
            count_card_map[count].append(item_power)
        count_list = tuple(count_card_map.keys())

        # 判断是否为一张
        if cards_type == CardOrder.CARD_ORDER_TYPE['一张']:
            result = len(cards) == 1
            power = cards[0].get_power()

        # 判断是否为一对
        elif cards_type == CardOrder.CARD_ORDER_TYPE['一对']:
            # 1. 计数只有1种
            # 2. 有数量为2个的牌
            # 3. 数量为2个的牌有1种
            result = len(count_card_map) == 1 \
                     and 2 in count_list \
                     and len(count_card_map[2]) == 1
            power = cards[0].get_power()

        # 判断是否为三张
        elif cards_type == CardOrder.CARD_ORDER_TYPE['三张']:
            # 1. 计数只有1种
            # 2. 有数量为3个的牌
            # 3. 数量为3个的牌有1种
            result = len(count_card_map) == 1 \
                     and 3 in count_list \
                     and len(count_card_map[3]) == 1
            power = cards[0].get_power()

        # 判断是否为双三张
        elif cards_type == CardOrder.CARD_ORDER_TYPE['双三张']:
            # 1. 计数只有1种
            # 2. 有数量为3个的牌
            # 3. 数量为3个的牌有2种
            result = len(count_card_map) == 1 \
                     and 3 in count_list \
                     and len(count_card_map[3]) == 2
            power = cards[0].get_power()

        # 判断是否为三带一
        elif cards_type == CardOrder.CARD_ORDER_TYPE['三带一']:
            # 1. 计数只有2种
            # 2. 有数量为3个的牌
            # 3. 有数量为1个的牌
            # 4. 数量为3个的牌有1种
            # 5. 数量为1个的牌有1种
            result = len(count_card_map) == 2 \
                     and 3 in count_list \
                     and 1 in count_list \
                     and len(count_card_map[3]) == 1 \
                     and len(count_card_map[1]) == 1
            power = count_card_map[3][0]

        # 判断是否为三带二
        elif cards_type == CardOrder.CARD_ORDER_TYPE['三带二']:
            # 1. 计数只有2种
            # 2. 有数量为3个的牌
            # 3. 有数量为2个的牌
            # 4. 数量为3个的牌有1种
            # 5. 数量为2个的牌有1种
            result = len(count_card_map) == 2 \
                     and 3 in count_list \
                     and 2 in count_list \
                     and len(count_card_map[3]) == 1 \
                     and len(count_card_map[2]) == 1
            power = count_card_map[3][0]

        # 判断是否为四带一
        elif cards_type == CardOrder.CARD_ORDER_TYPE['四带一']:
            # 1. 计数只有2种
            # 2. 有数量为4个的牌
            # 3. 有数量为1个的牌
            # 4. 数量为4个的牌有1种
            # 5. 数量为1个的牌有1种
            result = len(count_card_map) == 2 \
                     and 4 in count_list \
                     and 1 in count_list \
                     and len(count_card_map[4]) == 1 \
                     and len(count_card_map[1]) == 1
            power = count_card_map[4][0]

        # 判断是否为四带二
        elif cards_type == CardOrder.CARD_ORDER_TYPE['四带二']:
            # 1. 有数量为4个的牌
            # 2. 数量为4个的牌有1种
            # 3. 其他牌数量为2
            result = 4 in count_list \
                     and len(count_card_map[4]) == 1 \
                     and len(cards) - 4 == 2
            power = count_card_map[4][0]

        # 判断是否为四带两对
        elif cards_type == CardOrder.CARD_ORDER_TYPE['四带两对']:
            # 1. 计数只有2种
            # 2. 有数量为4个的牌
            # 3. 有数量为2个的牌
            # 4. 数量为4个的牌有1种
            # 5. 数量为2个的牌有2种
            result = len(count_card_map) == 2 \
                     and 4 in count_list \
                     and 2 in count_list \
                     and len(count_card_map[4]) == 1 \
                     and len(count_card_map[2]) == 2
            power = count_card_map[4][0]

        # 判断是否为顺子
        elif cards_type == CardOrder.CARD_ORDER_TYPE['顺子']:
            # 1. 计数只有1种
            # 2. 有数量为1个的牌
            # 3. 数量为1个的牌大于等于5种
            result = len(count_card_map) == 1 \
                     and 1 in count_list \
                     and len(count_card_map[1]) >= 5 \
                     and CardOrder.__is_continuous(count_card_map[1])
            power = min(count_card_map[1])  # 取最小值为权值

        # 判断是否为连对
        elif cards_type == CardOrder.CARD_ORDER_TYPE['连对']:
            # 1. 计数只有1种
            # 2. 有数量为2个的牌
            # 3. 数量为2个的牌大于等于3种
            # 4. 数量为2个的牌连续
            result = len(count_card_map) == 1 \
                     and 2 in count_list \
                     and len(count_card_map[2]) >= 3 \
                     and CardOrder.__is_continuous(count_card_map[2])
            power = min(count_card_map[2])  # 取最小值为权值

        # 判断是否为飞机
        elif cards_type == CardOrder.CARD_ORDER_TYPE['飞机']:
            # 1. 有数量为3个的牌
            # 2. 数量为3个的牌大于等于2
            # 3. 牌数为3的牌种类数量 等于 其他牌数量
            # 4. 数量为3个的牌连续
            result = 3 in count_list \
                     and len(count_card_map[3]) >= 2 \
                     and len(count_card_map[3]) == len(cards) - len(count_card_map[3]) * 3 \
                     and CardOrder.__is_continuous(count_card_map[3])
            power = min(count_card_map[3])  # 取最小值为权值

            # 特判特别的飞机（比如三个飞机带三个相同的牌）
            if not result:
                # 1. 有数量为3个的牌
                # 2. 数量为3个的牌大于等于3
                # 3. 牌数为3的牌种类数量-1 等于 其他牌数量+3
                # 4. 数量为3个的牌连续 有【牌数为3的牌种类数量-1】个连续的
                result = 3 in count_list \
                         and len(count_card_map[3]) >= 3 \
                         and len(count_card_map[3]) - 1 == len(cards) - len(count_card_map[3]) * 3 + 3
                count_card_map[3].sort()
                # 优先取最小的牌当做 带的牌
                if CardOrder.__is_continuous(count_card_map[3][1:]):
                    power = min(count_card_map[3][1:])  # 取最小值为权值
                elif CardOrder.__is_continuous(count_card_map[3][:-1]):
                    power = min(count_card_map[3][:-1])  # 取最小值为权值
                else:
                    raise MyException(MyException.EXCEPTION_CODE_TYPE.ERROR, "未找到有效权值")

        # 判断是否为飞机带对子
        elif cards_type == CardOrder.CARD_ORDER_TYPE['飞机带对子']:
            # 1. 计数只有2种
            # 2. 有数量为3个的牌
            # 3. 有数量为2个的牌
            # 4. 数量为3个的牌大于等于2
            # 5. 牌数为2的牌种类数量 等于 牌数为3的牌种类数量
            # 6. 数量为3个的牌连续
            result = len(count_card_map) == 2 \
                     and 3 in count_list \
                     and 2 in count_list \
                     and len(count_card_map[3]) >= 2 \
                     and len(count_card_map[2]) == len(count_card_map[3]) \
                     and CardOrder.__is_continuous(count_card_map[3])
            power = min(count_card_map[3])

            #  特判特别的飞机带对子（比如两个飞机带四个相同的牌）
            if not result:
                # 1. 有数量为3个的牌
                # 2. 只能有牌为3张、2张、4张的（所以只判断没有数量为1的牌）
                # 3. 数量为3个的牌大于等于2
                # 4. 除【数量为3个的牌】其他牌数量/2 等于 牌数为3的牌种类数量
                # 5. 数量为3个的牌连续
                result = 3 in count_list \
                         and 1 not in count_list \
                         and len(count_card_map[3]) >= 2 \
                         and (len(cards) - len(count_card_map[3]) * 3) / 2 == len(count_card_map[3]) \
                         and CardOrder.__is_continuous(count_card_map[3])
                power = min(count_card_map[3])

        # 判断是否为炸弹
        elif cards_type == CardOrder.CARD_ORDER_TYPE['炸弹']:
            # 1. 计数只有1种
            # 2. 有数量为4个的牌
            # 3. 数量为4个的牌有1种
            result = len(count_card_map) == 1 \
                     and 4 in count_list \
                     and len(count_card_map[4]) == 1
            power = cards[0].get_power()

        # 判断为王炸
        elif cards_type == CardOrder.CARD_ORDER_TYPE['王炸']:
            # 1. 计数只有1种
            # 2. 有数量为1个的牌
            # 3. 数量为1个的牌有2种
            # 4. 大王在其中
            # 5. 小王在其中
            result = len(count_card_map) == 1 \
                     and 1 in count_list \
                     and len(count_card_map[1]) == 2 \
                     and Card('大王', '').get_power() in count_card_map[1] \
                     and Card('小王', '').get_power() in count_card_map[1]
            power = Card('大王', '').get_power()
        return result, power

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

    # 判断数组是否连续
    @staticmethod
    def __is_continuous(arr):
        arr.sort()
        for i in range(1, len(arr)):
            if arr[i] != arr[i - 1] + 1:
                return False
        return True

    def get_power(self):
        return self.__power

    def get_type(self):
        return self.__type

    def get_size(self):
        return len(self.__cards)

    def get_card_str_list(self):
        return [str(card) for card in self.__cards]

    def __str__(self):
        return " ".join([str(card) for card in self.__cards])


# 定义游戏类（一局的游戏）
# 主要用来处理出牌逻辑
# 封装每个游戏步骤：叫分，出牌，判断出牌大小
class Play:

    def __init__(self, room, players):

        if len(players) != 3:
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ERROR, "玩家人数必须为3人")

        self.__room = room
        self.__players = players
        self.__cards = []
        self.__name_list = []  # 准备名称列表（名称:角色）
        self.__players_index = 0  # 正在操作的玩家下标
        self.__landlord_index = 0  # 地主下标
        self.__last_card_order = None  # 上一个出牌
        self.__last_players_index = 0  # 上一个出牌者的下标
        self.__free_deal = True  # 当前是否为任意牌（就是可以不用根据上次的出牌结果出的牌，可以出任意符合出牌逻辑的牌）

        self.__notify_deal = False  # 记录是否发送过出牌通知

        # 清空用户原有内容（原来的牌）
        for player in self.__players:
            player.clear()

    # 叫分阶段
    def marking(self):

        # 如果全为0分 则需要重新发牌，重新叫分
        while True:
            # 清空用户原有内容（原来的牌）
            for player in self.__players:
                player.clear()

            # 重新买一盒牌
            card_box = CardBox()
            card_box.create()

            # 发牌
            card_box.deal(self.__players, 17)

            # 玩家整理手中的牌
            for player in self.__players:
                player.sort_cards()

            # 展示每个玩家（牌）
            for player in self.__players:
                player.send_message(Message(my_card_list=player.get_card_str_list()))

            # 开始叫分
            max_mark = 0
            max_player_index = 0
            for playing_index in range(len(self.__players)):
                playing = self.__players[playing_index]
                self.__room.send_all_message(Message(f"等待【{playing.get_name()}】叫分"), playing_index)

                # 判断这个人是否叫分在正常范围内
                # 如果叫分有误则一直循环 直到叫分正确
                while True:
                    playing.send_message(Message("请叫分（0~3）", state=PLAY_STATE.MARKING))
                    msg = playing.receive_message()

                    # 如果接收的内容是一个非数字 则重新叫分
                    if not msg.isnumeric():
                        playing.send_message(Message("格式错误，请输入纯数字", state=PLAY_STATE.MARKING))
                        continue
                    mark = int(msg)

                    # 叫分正常 则跳出循环
                    if 0 <= mark <= 3:
                        # 修改用户名称 使得通过名称标记叫分大小
                        self.__name_list[playing_index] = playing.get_name() + f":{mark}分"
                        break

                    playing.send_message(Message("叫分范围有误，请重新叫分", state=PLAY_STATE.MARKING))

                self.__room.send_all_message(Message(f"【{playing.get_name()}】叫 {mark} 分", name_list=self.__name_list, state=PLAY_STATE.WAIT))

                # 判断叫分大小
                if mark > max_mark:
                    max_mark = mark
                    max_player_index = playing_index  # 标记叫分最大的那个人

                    # 分等于3直接结束叫分
                    if mark == 3:
                        break

            # 叫分完成准备开始游戏
            if max_mark != 0:
                self.__landlord_index = max_player_index
                self.__players_index = max_player_index
                self.__last_players_index = max_player_index

                # 准备名称列表（名称:角色）
                self.__name_list = []
                for playing_index in range(len(self.__players)):
                    role = ''
                    if playing_index == self.__landlord_index:
                        role = '地主'
                    else:
                        role = '农民'
                    self.__name_list.append(self.__players[playing_index].get_name() + ":" + role)

                # 摸底牌
                remain_cards = card_box.get_remain()
                self.__players[self.__landlord_index].add_cards(remain_cards)
                self.__players[self.__landlord_index].sort_cards()
                self.__players[self.__landlord_index].send_message(Message(my_card_list=self.__players[self.__landlord_index].get_card_str_list()))

                # 展示底牌
                self.__room.send_all_message(Message(f"地主是:{self.__players[self.__landlord_index].get_name()}", name_list=self.__name_list,
                                                     remain_card_list=[str(card) for card in remain_cards], state=PLAY_STATE.WAIT))
                break

    # 出牌阶段
    def deal(self):

        # 玩家轮换出牌
        while True:
            playing = self.__players[self.__players_index]
            try:
                card_count_list = []

                # 统计 每个玩家的剩余牌数
                for player in self.__players:
                    card_count_list.append(len(player.get_cards()))

                self.__room.send_all_message(Message(card_count_list=card_count_list, state=PLAY_STATE.WAIT))

                # 出牌提醒
                # 如果上次出牌者是本人，则说明没人出牌压它，所以可以出任意牌了
                if self.__last_players_index == self.__players_index:
                    self.__last_card_order = None
                    self.__free_deal = True

                # 出一次牌
                if self.__free_deal:
                    self.free_deal_cards(playing)
                else:
                    self.normal_deal_cards(playing)

                # 迭代下一个玩家
                self.__players_index += 1
                self.__players_index %= len(self.__players)
                self.__free_deal = False
                self.__notify_deal = False

                # 判断是否胜利
                result = False
                for playing_index in range(len(self.__players)):
                    card_list = self.__players[playing_index].get_cards()
                    if len(card_list) == 0:
                        self.__room.send_all_message(Message(f"【{self.__name_list[playing_index]}】胜利！5秒后结束本局游戏", state=PLAY_STATE.WAIT))
                        time.sleep(5)
                        self.__room.stop_play()
                        result = True
                        break
                if result:
                    break

            except MyException as ex:
                if ex.get_code() == MyException.EXCEPTION_CODE_TYPE.ERROR:
                    raise ex
                elif ex.get_code() == MyException.EXCEPTION_CODE_TYPE.ALL:
                    self.__room.send_all_message(Message(ex.get_message()))
                elif ex.get_code() == MyException.EXCEPTION_CODE_TYPE.ONE:
                    playing.send_message(Message(ex.get_message()))
                else:
                    print(ex.get_message())

    # 出一次任意牌
    def free_deal_cards(self, playing):
        if self.__notify_deal != True:
            self.__room.send_all_message(Message(f"轮到【{self.__name_list[self.__players_index]}】出任意牌了", last_card_list=[]))
            self.__notify_deal = True
        playing.send_message(Message(state=PLAY_STATE.FREE))

        # 接受用户指令（出的牌或者是不出）
        commend = playing.receive_message().strip()

        # 用户不出牌
        if commend == "不出" or commend.lower() == "pass":
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ONE, "本次你为任意牌，必须出牌")

        card_str_list = commend[:-2].split()
        cards_type = commend[-2:]
        if not cards_type.isnumeric():
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ERROR, "出牌类型需要根据数值来判断")

        card_list = CardOrder.make_card_list(card_str_list)
        card_order = CardOrder(card_list, CardOrder.CARD_ORDER_TYPE(int(cards_type)))

        # 移除玩家手中的牌
        playing.remove_cards(card_list)

        # 展示出牌
        playing.send_message(Message(my_card_list=playing.get_card_str_list()))
        self.__room.send_all_message(Message(last_card_player_index=self.__players_index,
                                             last_card_list=card_order.get_card_str_list(),
                                             last_card_type=card_order.get_type().name,
                                             state=PLAY_STATE.WAIT))

        # 存储本次出牌
        self.__last_card_order = card_order
        self.__last_players_index = self.__players_index

    # 出一次普通牌
    def normal_deal_cards(self, playing):
        if self.__notify_deal != True:
            self.__room.send_all_message(Message(f"轮到【{self.__name_list[self.__players_index]}】出牌了"))
            self.__notify_deal = True
        playing.send_message(Message(state=PLAY_STATE.PLAYING))

        # 接受用户指令（出的牌或者是不出）
        commend = playing.receive_message().strip()

        # 用户不出牌
        if commend == "不出" or commend.lower() == "pass":  # 不出提醒消息
            self.__room.send_all_message(Message(f"【{self.__name_list[self.__players_index]}】选择了不出", state=PLAY_STATE.WAIT))
            return

        card_str_list = commend[:-2].split()
        cards_type = commend[-2:]
        if not cards_type.isnumeric():
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ERROR, "出牌类型需要根据数值来判断")

        card_list = CardOrder.make_card_list(card_str_list)
        card_order = CardOrder(card_list, CardOrder.CARD_ORDER_TYPE(int(cards_type)))

        # 与上局的牌比较大小
        if not self.compare_last(card_order):
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ONE, "出牌不符合规则")

        # 移除玩家手中的牌
        playing.remove_cards(card_list)

        # 展示出牌
        playing.send_message(Message(my_card_list=playing.get_card_str_list()))
        self.__room.send_all_message(Message(last_card_player_index=self.__players_index,
                                             last_card_list=card_order.get_card_str_list(),
                                             last_card_type=card_order.get_type().name,
                                             state=PLAY_STATE.WAIT))

        # 存储本次出牌
        self.__last_card_order = card_order
        self.__last_players_index = self.__players_index

    # 与上局的牌比较大小
    # 返回值   True    出牌比得过上局
    #         False   出牌不比上局大 或者 与上局牌类型不符
    def compare_last(self, card_order):

        # 如果是王炸直接炸掉上局的牌
        if card_order.get_type() == card_order.CARD_ORDER_TYPE["王炸"]:
            return True

        # 如果是炸弹
        elif card_order.get_type() == card_order.CARD_ORDER_TYPE["炸弹"]:
            # 如果上次出牌也是炸弹 则需要判断炸弹的大小
            if self.__last_card_order.get_type() == card_order.CARD_ORDER_TYPE["炸弹"] \
                    and card_order.get_power() <= self.__last_card_order.get_power():
                return False
            else:
                return True  # 上局不为炸弹 或者 比上局的炸弹更大
        else:
            # 判断普通牌 出牌规则
            # 1. 必须与上次出牌类型相同
            # 2. 必须大于上次出牌的权值
            # 3. 如果为 【"顺子", "连对", "飞机", "飞机带对子"】 则必须与上次出牌的数量相等
            if card_order.get_type() != self.__last_card_order.get_type() \
                    or card_order.get_power() <= self.__last_card_order.get_power() \
                    or (str(card_order.get_type().name) in ["顺子", "连对", "飞机", "飞机带对子"] \
                        and card_order.get_size() != self.__last_card_order.get_size()):
                return False
            else:
                return True

        return False

    # 开始游戏
    def start(self):

        # 设置玩家名称
        for playing in self.__players:
            self.__name_list.append(playing.get_name())

        for i in range(len(self.__players)):
            player = self.__players[i]
            player.send_message(Message("开始游戏!", name_list=self.__name_list, my_index=i))

        # 叫分
        self.marking()

        # 出牌
        self.deal()


# 定义桌子类
class Room:

    # 构造方法
    def __init__(self, name):
        self.__name = name
        self.__players = []

    # 获取房间名称
    def get_name(self):
        return self.__name

    # 发送全体消息
    def send_all_message(self, message, exclude=-1):
        for player_index in range(len(self.__players)):
            if player_index == exclude:
                continue
            self.__players[player_index].send_message(message)

    # 结束本次游戏
    def stop_play(self):
        for player in self.__players:
            player.send_stop_play()

    # 添加一个玩家
    def add_player(self, player):
        if len(self.__players) >= 3:
            player.send_info("每桌最多3位玩家，玩家已经满了")
            raise MyException(MyException.EXCEPTION_CODE_TYPE.ONE, "每桌最多3位玩家，玩家已经满了")

        self.__players.append(player)

        name_list = []
        for player in self.__players:
            name_list.append(player.get_name())
        for i in range(len(self.__players)):
            player = self.__players[i]
            player.send_message(Message("【" + player.get_name() + "】加入了房间", name_list=name_list, my_index=i))

    def remove_player(self, item):
        self.__players.remove(item)

        name_list = []
        for player in self.__players:
            name_list.append(player.get_name())

        for i in range(len(self.__players)):
            player = self.__players[i]
            player.send_message(Message(f"【{item.get_name()}】退出了房间", name_list=name_list, my_index=i))

        self.stop_play()

    # 重复游戏
    def while_play(self):
        try:
            while True:
                self.play()

                if len(self.__players) != 3:
                    break

        except MyException as ex:
            print(str(ex))

    # 开始游戏
    def play(self):

        if len(self.__players) != 3:
            self.send_all_message(Message("等待其他玩家加入"))
            return

        p = Play(self, self.__players)
        p.start()


# 测试
def test():
    try:
        card = CardOrder([Card("3", "♥")], CardOrder.CARD_ORDER_TYPE["一张"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠")], CardOrder.CARD_ORDER_TYPE["一对"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆")], CardOrder.CARD_ORDER_TYPE["三张"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("4", "♥"), Card("4", "♠"), Card("4", "◆")],
                         CardOrder.CARD_ORDER_TYPE["双三张"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("4", "♥")],
                         CardOrder.CARD_ORDER_TYPE["三带一"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("4", "♥"), Card("4", "♠")],
                         CardOrder.CARD_ORDER_TYPE["三带二"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("3", "♣"), Card("4", "♥")],
                         CardOrder.CARD_ORDER_TYPE["四带一"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("3", "♣"), Card("4", "♥"), Card("4", "♠")],
                         CardOrder.CARD_ORDER_TYPE["四带二"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("3", "♣"), Card("4", "♥"), Card("5", "♠")],
                         CardOrder.CARD_ORDER_TYPE["四带二"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("3", "♣"),
                          Card("4", "♥"), Card("4", "♠"), Card("5", "♠"), Card("5", "◆")],
                         CardOrder.CARD_ORDER_TYPE["四带两对"])
        assert card.get_power() == 3

        try:
            card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "◆"), Card("3", "♣"), Card("5", "♥"),
                              Card("4", "♠"), Card("5", "♠"), Card("5", "◆")],
                             CardOrder.CARD_ORDER_TYPE["四带两对"])
        except Exception as ex:
            pass
        else:
            assert False, "四带两对未通过"

        card = CardOrder([Card("3", "♥"), Card("4", "♥"), Card("5", "♠"), Card("6", "♠"), Card("7", "♠")],
                         CardOrder.CARD_ORDER_TYPE["顺子"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("4", "♥"), Card("5", "♠"), Card("5", "♥"), Card("3", "♠"), Card("4", "♠")],
                         CardOrder.CARD_ORDER_TYPE["连对"])
        assert card.get_power() == 3

        try:
            card = CardOrder([Card("3", "♥"), Card("4", "♥"), Card("5", "♠"), Card("5", "♥"), Card("3", "♠"), Card("3", "♠")],
                             CardOrder.CARD_ORDER_TYPE["连对"])
        except Exception as ex:
            pass
        else:
            assert False, "连对未通过"

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "♠"), Card("4", "◆"),
                          Card("5", "♥"), Card("5", "♠")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "♠"), Card("4", "◆"),
                          Card("5", "♥"), Card("6", "♠")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "♠"), Card("4", "◆"),
                          Card("5", "♥"), Card("5", "♠"), Card("5", "◆"), Card("5", "♣")],
                         CardOrder.CARD_ORDER_TYPE["飞机带对子"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "♠"), Card("4", "◆"),
                          Card("5", "♥"), Card("5", "♠"), Card("6", "◆"), Card("6", "♣")],
                         CardOrder.CARD_ORDER_TYPE["飞机带对子"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("6", "◆"), Card("6", "♠")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 4

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("6", "◆"), Card("6", "♠"),
                          Card("7", "♥"), Card("7", "◆"), Card("7", "♠"),
                          Card("8", "♥")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 4

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("7", "◆"), Card("8", "♠")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("6", "◆"),
                          Card("7", "♥"), Card("7", "◆"),
                          Card("8", "♥"), Card("8", "◆")],
                         CardOrder.CARD_ORDER_TYPE["飞机带对子"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("6", "◆"), Card("6", "♠"),
                          Card("7", "♥"), Card("7", "◆"),
                          Card("8", "♥"), Card("8", "◆")],
                         CardOrder.CARD_ORDER_TYPE["飞机"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "◆"), Card("3", "♠"),
                          Card("4", "♥"), Card("4", "◆"), Card("4", "♠"),
                          Card("5", "♥"), Card("5", "◆"), Card("5", "♠"),
                          Card("6", "♥"), Card("6", "◆"), Card("6", "♠"),
                          Card("7", "♥"), Card("7", "◆"), Card("7", "♠"), Card("7", "♣"),
                          Card("8", "♥"), Card("8", "◆"), Card("8", "♠"), Card("8", "♣")],
                         CardOrder.CARD_ORDER_TYPE["飞机带对子"])
        assert card.get_power() == 3

        card = CardOrder([Card("3", "♥"), Card("3", "♠"), Card("3", "♣"), Card("3", "◆")],
                         CardOrder.CARD_ORDER_TYPE["炸弹"])
        assert card.get_power() == 3

        card = CardOrder([Card("大王", ""), Card("小王", "")], CardOrder.CARD_ORDER_TYPE["王炸"])
        assert card.get_power() == Card("大王", "").get_power()

        assert len(set([Card("3", "♥"), Card("3", "♠"), Card("3", "♣"), Card("3", "◆")])) == 4

        assert CardOrder([Card("3", "♥"), Card("3", "♥"), Card("3", "♥"), Card("大王", "")],
                         CardOrder.CARD_ORDER_TYPE["三带一"]).get_power() == 3

    except MyException as ex:
        print("没有通过测试")
        print(ex.get_message())
        raise ex
    except Exception as ex:
        print("没有通过测试")
        print(ex.__str__())
        raise ex


if __name__ == '__main__':

    test()

    room_map = {}

    # 创建 socket 对象
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = "0.0.0.0"
    port = 9999
    serversocket.bind((host, port))
    serversocket.listen(5)

    index = 0
    while True:
        try:
            # 建立客户端连接
            clientsocket, addr = serversocket.accept()
            name = str(clientsocket.recv(20).decode('utf-8')).strip().split("\n")
            room_name = name[0].strip()
            player_name = name[1].strip()

            if room_name not in room_map.keys():
                room_map[room_name] = Room(room_name)

            room = room_map[room_name]
            room.add_player(Player(player_name, clientsocket, addr, room))

            Thread(target=room.while_play).start()
        except MyException as ex:
            print(ex)
        except Exception as ex:
            print(ex)
