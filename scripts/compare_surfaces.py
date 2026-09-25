import trimesh,numpy as np,json
from pathlib import Path
from trimesh.ray.ray_pyembree import RayMeshIntersector
R=Path(__file__).resolve().parent.parent
a=trimesh.load(R/'reference/preferred.glb',force='scene').to_geometry()
b=trimesh.load(R/'models/model.glb',force='scene').to_geometry()
ra=RayMeshIntersector(a);rb=RayMeshIntersector(b)
center=a.bounds.mean(axis=0);scale=150/a.extents[1]
results=[]
for label,vec in [('front',[0,0,-1]),('back',[0,0,1]),('left',[1,0,0]),('right',[-1,0,0]),('top',[0,-1,0]),('bottom',[0,1,0]),('front-left',[1,0,-1]),('front-right',[-1,0,-1]),('back-left',[1,0,1]),('back-right',[-1,0,1])]:
    d=np.array(vec,dtype=float);d/=np.linalg.norm(d)
    up=np.array([0,1,0]) if abs(d[1])<.9 else np.array([0,0,1])
    u=np.cross(d,up);u/=np.linalg.norm(u);v=np.cross(u,d)
    pu=(a.vertices-center)@u;pv=(a.vertices-center)@v
    xx,yy=np.meshgrid(np.linspace(pu.min()-.01,pu.max()+.01,300),np.linspace(pv.min()-.01,pv.max()+.01,400))
    origin=center+xx.ravel()[:,None]*u+yy.ravel()[:,None]*v-d*3
    directions=np.tile(d,(len(origin),1))
    def depths(intersector):
        loc,index,_=intersector.intersects_location(origin,directions,multiple_hits=False)
        out=np.full(len(origin),np.nan);out[index]=np.sum((loc-origin[index])*d,axis=1)
        return out
    x=depths(ra);y=depths(rb);both=np.isfinite(x)&np.isfinite(y)
    delta=np.abs(x[both]-y[both])*scale
    row={'view':label,'rays':len(x),'source_hits':int(np.isfinite(x).sum()),'lost_silhouette_rays':int((np.isfinite(x)&~np.isfinite(y)).sum()),'added_silhouette_rays':int((~np.isfinite(x)&np.isfinite(y)).sum()),'max_surface_difference_mm':float(delta.max()),'p99_surface_difference_mm':float(np.quantile(delta,.99)),'rays_over_0_1mm':int((delta>.1).sum())}
    results.append(row);print(row,flush=True)
json.dump({'method':'First ray hit from ten orthographic directions, 300x400 rays each, compared at 150 mm height. Finite sampling does not prove exact surface equality.','views':results},open(R/'reports/surface-comparison.json','w'),indent=2)
