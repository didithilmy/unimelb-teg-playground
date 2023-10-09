from decimal import Decimal, getcontext

# getcontext().prec = 8

f1 = 1758.0204 
f2 = 1725.0 
f3 = -13172.06081e-12
f4 = 8825.0

print(float(Decimal(str(f3)) + Decimal(str(f4))))