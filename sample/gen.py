#! python3
import random
r=random.Random()

case=int(input())
r.seed(int(input()))

print(r.randrange(100+case*100))
print(r.randrange(100+case*100))