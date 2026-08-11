import weakref

class Dog:
    def __init__(self, name):
        self.name = name

dog = Dog("旺财")
dog1 = Dog("旺财1")

# 1. 强引用列表
# strong_list = [dog,dog1] 
# 2. 弱引用列表
weak_list = [weakref.ref(dog), weakref.ref(dog1)] 

print(dog,dog1)
print(weak_list)  # 输出: <__main__.Dog object...> (还能找到狗)

# 删除外部强引用
del dog

# 此时，strong_list 依然死死抱着对象
# print(strong_list[0].name)  # 输出: 旺财 (内存未释放)

# 但是，weak_list 里的对象已经被垃圾回收了
print(weak_list[0]().name)       # 输出: None (狗已经没了)