# coding: utf-8
import netcdf
import netcdftime
from netcdf4
import netcdf4
import netCDF4
import netCDF4 as n
cdf = n.Dataset("./ts.cdf4", 'w', format="NETCDF4")
cdf.createGroup("ts")
ts = cdf.createGroup("ts")
cdf.groups()
cdf.groups
ts = cdf.groups['ts']
ts.createDimension?
ts.createDimension("pixel", 3)
from timestream.parse import ts_iter_images
from timestream.parse import ts_iter_numpy
imgs = ts_iter_images("./tests/data/timestreams/BVZ0022-GC05L-CN650D-Cam07~fullres-orig/")
mats = ts_iter_numpy(imgs)
mats  = list(mats)
mats
mat1 = mats[0][1]
mat1.shape
cdf.close()
cdf = n.Dataset("./ts.cdf4", 'w', format="NETCDF4")
cdf.groups()
cdf.groups
cdf.createVariable?
cdf.createVariable?
cdf.createVariable('ts')
cdf.createVariable?
cdf.createVariable('ts', 'u1')
cdf.variables()
cdf.variables
ts =cdf.variables['ts']
ts.shape
ts.dimensions
cdf.createDimension?
mat1.shape
cdf.createDimension('z', 3)
cdf.createDimension('y', 3356)
cdf.createDimension('y', 3456)
cdf.variables['y']
cdf.variables
cdf.dimensions
del(cdf.dimensions['y'])
cdf.dimensions
cdf.createDimension('y', 3456)
cdf.close()
cdf = n.Dataset("./ts.cdf4", 'w', format="NETCDF4")
cdf.createVariable('ts', 'u1')
mat1.shape
x, y, z = mat1.shape
cdf.dimensions
cdf.createDimension('y', y)
cdf.createDimension('z', z)
cdf.createDimension('x', x)
cdf.dimensions
cdf.vltypes?
cdf.variables['ts
cdf.variables['ts']
ts = cdf.variables['ts']
ts.dimensions
ts.ndim
ts.ndim = 4
cdf.close()
cdf = n.Dataset("./ts.cdf4", 'w', format="NETCDF4")
%save --help
%save?
save -r 1-69
