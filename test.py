class TestProperty:
    def __init__(self, value):
        self._type = value
    
    # 不使用 @property
    def type_without_property(self):
        return self._type
    
    # 使用 @property
    @property
    def type_with_property(self):
        return self._type
    
    # 另一个测试用例
    @property
    def computed_value(self):
        """这是一个计算属性"""
        return len(self._type) * 2

# 测试代码
def test_property():
    obj = TestProperty("hello")
    
    print("=== 测试不使用 @property 的情况 ===")
    print(f"直接访问: {obj.type_without_property}")  # 输出方法对象
    print(f"方法调用: {obj.type_without_property()}")  # 输出实际值
    
    print("\n=== 测试使用 @property 的情况 ===")
    print(f"直接访问: {obj.type_with_property}")  # 输出实际值
    print(f"方法调用: {obj.type_with_property()}")  # 会报错，因为不是方法
    
    print("\n=== 测试计算属性 ===")
    print(f"计算属性: {obj.computed_value}")  # 输出 10 (5*2)
    try:
        print(f"方法调用: {obj.computed_value()}")  # 会报错
    except TypeError as e:
        print(f"错误: {e}")

# 运行测试
test_property()
