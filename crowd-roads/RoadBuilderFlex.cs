using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;
using Michsky.MUIP;
using System;
using System.Linq;
using ITS.Utils;
using UnityEngine.EventSystems;
using System.Reflection.Emit;
using UnityEditor.PackageManager;

public class RoadBuilderFlex : MonoBehaviour
{
    public static TSLaneInfo.VehicleType[] ROAD_VEHICLE_TYPES = new TSLaneInfo.VehicleType[] {
        TSLaneInfo.VehicleType.Light,
        TSLaneInfo.VehicleType.Medium,
        TSLaneInfo.VehicleType.Taxi,
        TSLaneInfo.VehicleType.Bus,
        TSLaneInfo.VehicleType.Heavy
    };

    public static TSLaneInfo.VehicleType[] FOOTPATH_VEHICLE_TYPES = new TSLaneInfo.VehicleType[] {
        TSLaneInfo.VehicleType.Pedestrians
    };

    public ERRoadNetwork roadNetwork;
    public GameObject itsManager, trafficLightPrefab;
    public bool rightHandDriving = false;

    [SerializeField] public CustomTrafficSpawner.VehicleConfig[] vehicles;

    private TSMainManager tsMainManager;
    private Dictionary<ERRoad, List<TSLaneInfo>> roadLaneMap = new Dictionary<ERRoad, List<TSLaneInfo>>();
    private Dictionary<Vector3, ERConnection> connectorMap = new();
    private bool simulationEnabled = false;

    [System.Serializable]
    public class TrafficLightConfig
    {
        public TSTrafficLight.LightType type;
        public int duration;
    }

    void Start()
    {
        roadNetwork = new ERRoadNetwork();
        ERModularBase modularBase = roadNetwork.roadNetwork;
        modularBase.displayLaneData = true; // Required to allow iTS to connect lanes at intersections
        modularBase.rightHandDriving = rightHandDriving ? 1 : 0;
        roadNetwork.LoadConnections();
        tsMainManager = itsManager.GetComponent<TSMainManager>();
    }

    public void StartSimulation()
    {
        simulationEnabled = true;
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StartSpawner();
        }
    }

    public void StopSimulation()
    {
        simulationEnabled = false;
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StopSpawner();
            spawner.DestroyAllCars();
        }
    }

    public void ProcessNewRoad(ERRoad road)
    {
        road = ProcessNewRoad(road, 0);
        ProcessNewRoad(road, road.GetMarkerCount() - 1);
    }

    public ERRoad ProcessNewRoad(ERRoad currentRoad, int markerIndex)
    {
        int i = markerIndex;
        var currentRoadMarkerPos = currentRoad.GetMarkerPosition(i);

        ERConnection connection = GetAttachedERConnectionIfAny(currentRoad, i, currentRoad.GetWidth() / 2);
        if (connection != null)
        {
            connection.prefabScript.tCrossing = true;
            if (i == 0)
            {
                currentRoad.ConnectToStart(connection);
            }
            else
            {
                currentRoad.ConnectToEnd(connection);
            }
            connection.Refresh();
            connection.ResetLaneConnectors();
        }
        else
        {
            ERRoad attachedRoad = GetAttachedRoadIfAny(out int splinePointIndex, GetRoadObjects(), currentRoad, i, currentRoad.GetWidth() / 2);
            if (attachedRoad != null)
            {
                ClearITSLane(attachedRoad);
                attachedRoad.InsertFlexConnector(currentRoadMarkerPos, currentRoad, i, out ERRoad road3);
                CreateITSLane(attachedRoad, ROAD_VEHICLE_TYPES);
                CreateITSLane(road3, ROAD_VEHICLE_TYPES);
            }
            else
            {
                HashSet<ERRoad> connectedRoads = GetConnectedRoads(GetRoadObjects(), currentRoad);
                foreach (ERRoad connectedRoad in connectedRoads)
                {
                    ClearITSLane(connectedRoad);
                    currentRoad = roadNetwork.ConnectRoads(currentRoad, connectedRoad);
                }
            }
        }

        CreateITSLane(currentRoad, ROAD_VEHICLE_TYPES);
        CreateITSConnections(GetRoadObjects());
        tsMainManager.ProcessJunctions(false, 0f);

        return currentRoad;
    }

    public ERRoad CreateRoad(string name, ERRoadType roadType, Vector3 startCoord, float width = 6f)
    {
        ERRoad road = roadNetwork.CreateRoad(name, roadType);
        road.SetWidth(roadType.roadWidth);
        road.AddMarker(startCoord);
        road.AddMarker(startCoord);
        return road;
    }

    public void UpdateRoadEndCoord(ERRoad road, Vector3 coord)
    {
        road.DeleteMarker(1);
        road.InsertMarker(coord);
    }

    public ERRoad CreateFootpath(string name, Vector3 startCoord, bool crosswalk = false, float width = 3f)
    {
        ERRoadType roadType = roadNetwork.GetRoadTypeByName(!crosswalk ? "Footpath" : "Crosswalk");
        ERRoad road = roadNetwork.CreateRoad(name, roadType);
        road.SetWidth(width);
        road.AddMarker(startCoord + new Vector3(0, 0.1f, 0));
        road.AddMarker(startCoord + new Vector3(0, 0.1f, 0));
        road.SetMeshCollider(false);
        return road;
    }

    public void UpdateFootpathEndCoord(ERRoad road, Vector3 coord)
    {
        road.DeleteMarker(1);
        road.InsertMarker(coord + new Vector3(0, 0.1f, 0));
    }

    public void ProcessNewFootpath(ERRoad footpath)
    {
        footpath = ProcessNewFootpath(footpath, 0);
        ProcessNewFootpath(footpath, footpath.GetMarkerCount() - 1);
    }
    public ERRoad ProcessNewFootpath(ERRoad footpath, int markerIndex)
    {
        int i = markerIndex;
        var currentRoadMarkerPos = footpath.GetMarkerPosition(i);

        ERConnection connection = GetAttachedERConnectionIfAny(footpath, i, footpath.GetWidth() / 2);
        if (connection != null)
        {
            connection.prefabScript.tCrossing = true;
            if (i == 0)
            {
                footpath.ConnectToStart(connection);
            }
            else
            {
                footpath.ConnectToEnd(connection);
            }
            // Set corner radius
            foreach (ERConnectionSibling sibling in connection.prefabScript.siblings)
                sibling.radius = 1;
            connection.Refresh();
            connection.ResetLaneConnectors();
        }
        else
        {
            ERRoad attachedRoad = GetAttachedRoadIfAny(out int splinePointIndex, GetFootpathObjects(), footpath, i, footpath.GetWidth() / 2);
            if (attachedRoad != null)
            {
                ERConnection flexConnector = attachedRoad.InsertFlexConnector(currentRoadMarkerPos, footpath, i, out ERRoad road3);

                // Set corner radius
                foreach (ERConnectionSibling sibling in flexConnector.prefabScript.siblings)
                    sibling.radius = 1;
                flexConnector.Refresh();
            }
            else
            {
                HashSet<ERRoad> connectedRoads = GetConnectedRoads(GetFootpathObjects(), footpath);
                foreach (ERRoad connectedRoad in connectedRoads)
                {
                    footpath = roadNetwork.ConnectRoads(footpath, connectedRoad);
                }
            }
        }

        return footpath;
    }

    public Vector3[] GetFootpathSplinePoints(ERRoad footpath)
    {
        Vector3[] leftSplinePoints = footpath.GetSplinePointsLeftSide();
        Vector3[] rightSplinePoints = footpath.GetSplinePointsRightSide();
        return leftSplinePoints.Concat(rightSplinePoints).ToArray();
    }

    public float GetFootpathWidth(ERRoad footpath)
    {
        float footpathWidth = footpath.GetWidth();
        return footpathWidth;
    }

    public HashSet<ERRoad> GetConnectedFootpaths(ERRoad currentRoad)
    {
        Vector3 startCoord = currentRoad.GetMarkerPosition(0);
        Vector3 endCoord = currentRoad.GetMarkerPosition(1);
        HashSet<ERRoad> roads = new HashSet<ERRoad>();
        ERRoad[] roadObjects = GetFootpathObjects();
        foreach (ERRoad road in roadObjects)
        {
            if (road == currentRoad) continue;
            Vector3[] markerPositions = road.GetMarkerPositions();
            foreach (Vector3 pos in markerPositions)
            {
                if (pos == startCoord || pos == endCoord)
                {
                    roads.Add(road);
                    break;
                }
            }
        }
        return roads;
    }

    public GameObject CreateTrafficLight(Vector3 coord, bool yellowLightsStopTraffic = true)
    {
        GameObject trafficLightObj = Instantiate(trafficLightPrefab, coord, Quaternion.identity);
        TSTrafficLight trafficLight = trafficLightObj.GetComponent<TSTrafficLight>();
        trafficLight.yellowLightsStopTraffic = yellowLightsStopTraffic;
        return trafficLightObj;
    }

    public void UpdateTrafficLightCoord(GameObject trafficLight, Vector3 coord, float planeRotationDegree = 0)
    {
        trafficLight.transform.position = coord;
        trafficLight.transform.rotation = Quaternion.identity * Quaternion.Euler(0, planeRotationDegree, 0);
    }

    public void ConnectLaneToTrafficLight(TSTrafficLight trafficLight, TSLaneInfo fromLane, TSLaneInfo toLane)
    {
        int fromLaneIndex = tsMainManager.lanes.FindIndex(fromLane);
        foreach (var connector in fromLane.connectors)
        {
            if (connector.NextLane == toLane)
            {
                int connectorIndex = fromLane.connectors.FindIndex(connector);
                bool connectionExists = trafficLight.pointsNormalLight.Exists(x => x.lane == fromLaneIndex && x.connector == connectorIndex);
                if (!connectionExists)
                {
                    trafficLight.pointsNormalLight.Add(new TSTrafficLight.TSPointReference()
                    {
                        lane = fromLaneIndex,
                        connector = connectorIndex,
                        point = 0
                    });
                }
            }
        }
    }

    public void DisconnectLaneFromTrafficLight(TSTrafficLight trafficLight, TSLaneInfo fromLane, TSLaneInfo toLane)
    {
        int fromLaneIndex = tsMainManager.lanes.FindIndex(fromLane);
        foreach (var connector in fromLane.connectors)
        {
            if (connector.NextLane == toLane)
            {
                int connectorIndex = fromLane.connectors.FindIndex(connector);
                List<TSTrafficLight.TSPointReference> pointReferences = trafficLight.pointsNormalLight.FindAll(x => x.lane == fromLaneIndex && x.connector == connectorIndex);
                foreach (TSTrafficLight.TSPointReference pointReference in pointReferences)
                {
                    trafficLight.pointsNormalLight.Remove(pointReference);
                }
            }
        }
    }

    public List<TSLaneInfo> GetTrafficLightConnectedLanes(TSTrafficLight trafficLight)
    {
        var outList = new List<TSLaneInfo>();
        foreach (var points in trafficLight.pointsNormalLight)
        {
            TSLaneInfo lane = tsMainManager.lanes[points.lane];
            outList.Add(lane);
        }
        return outList;
    }

    public void SetTrafficLightDurations(TSTrafficLight trafficLight, TrafficLightConfig[] configs)
    {
        trafficLight.lights.Clear();
        foreach (TrafficLightConfig config in configs)
        {
            trafficLight.lights.Add(new TSTrafficLight.TSLight()
            {
                lightType = config.type,
                lightTime = config.duration,
                lightMeshRenderer = trafficLight.gameObject.GetComponentInChildren<MeshRenderer>()
            });
        }
    }

    public CustomTrafficSpawner CreateTrafficSpawner(Vector3 coord, float radius = 0.00001f, float secondsBetweenSpawn = 1f)
    {
        GameObject trafficSpawnerGameObject = new GameObject("Traffic Spawner");
        trafficSpawnerGameObject.transform.position = coord + new Vector3(0, 0.01f, 0); // Add to prevent clash with the plane
        CustomTrafficSpawner trafficSpawner = trafficSpawnerGameObject.AddComponent<CustomTrafficSpawner>();
        trafficSpawner.vehicles = vehicles;
        trafficSpawner.secondsBetweenCars = secondsBetweenSpawn;
        trafficSpawner.radius = radius;

        if (simulationEnabled)
        {
            trafficSpawner.StartSpawner();
        }

        return trafficSpawner;
    }

    public void UpdateTrafficSpawnerRadius(CustomTrafficSpawner trafficSpawner, float radius)
    {
        trafficSpawner.radius = radius;
    }

    public void UpdateTrafficSpawnerInterval(CustomTrafficSpawner spawner, float secondsBetweenCars)
    {
        spawner.secondsBetweenCars = secondsBetweenCars;
    }

    public HashSet<ERRoad> GetConnectedRoads(ERRoad[] roadObjects, ERRoad currentRoad)
    {
        Vector3 startCoord = currentRoad.GetMarkerPosition(0);
        Vector3 endCoord = currentRoad.GetMarkerPosition(1);
        HashSet<ERRoad> roads = new HashSet<ERRoad>();
        foreach (ERRoad road in roadObjects)
        {
            if (road == currentRoad) continue;
            Vector3[] markerPositions = road.GetMarkerPositions();
            foreach (Vector3 pos in markerPositions)
            {
                if (pos == startCoord || pos == endCoord)
                {
                    roads.Add(road);
                    break;
                }
            }
        }
        return roads;
    }

    private void ClearITSLane(ERRoad road)
    {
        if (roadLaneMap.ContainsKey(road))
        {
            // Delete all lanes
            foreach (TSLaneInfo lane in roadLaneMap[road])
            {
                int laneIndex = tsMainManager.lanes.FindIndex(lane);
                tsMainManager.RemoveLane(laneIndex, null);
            }
            roadLaneMap[road].Clear();
        }
    }

    private TSLaneInfo[] CreateITSLane(ERRoad road, TSLaneInfo.VehicleType[] vehicleTypes = null, bool reverse = false, float tolerance = 0.4f, int laneWidth = 2)
    {
        if (roadLaneMap.ContainsKey(road))
        {
            // Delete all lanes
            ClearITSLane(road);
        }
        else
        {
            roadLaneMap[road] = new List<TSLaneInfo>();
        }

        var laneCount = road.GetLaneCount();
        TSLaneInfo[] lanes = new TSLaneInfo[laneCount];

        for (int laneIndex = 0; laneIndex < laneCount; laneIndex++)
        {
            var laneData = road.GetLaneData(laneIndex);
            var points = (reverse ? laneData.points.Reverse() : laneData.points).ToArray();
            tsMainManager.AddLane<TSLaneInfo>(points, tolerance);
            TSLaneInfo laneInfo = tsMainManager.lanes.Last();
            laneInfo.laneWidth = laneWidth;

            if (vehicleTypes != null)
            {
                laneInfo.vehicleType = 0;
                foreach (TSLaneInfo.VehicleType vehicleType in vehicleTypes)
                {
                    laneInfo.vehicleType = laneInfo.vehicleType.Add(vehicleType);
                }
            }

            roadLaneMap[road].Add(laneInfo);
            lanes[laneIndex] = laneInfo;
        }

        return lanes;
    }

    private void CreateITSConnections(ERRoad[] roads)
    {
        foreach (ERRoad road in roads)
        {
            var laneCount = road.GetLaneCount();
            for (int laneIndex = 0; laneIndex < laneCount; laneIndex++)
            {
                ERConnection firstConnection = road.GetConnectionAtStart(out int firstConnectionIndex);
                if (firstConnection != null) AddITSConnection(firstConnection, firstConnectionIndex, laneIndex);

                ERConnection secondConnection = road.GetConnectionAtEnd(out int secondConnectionIndex);
                if (secondConnection != null) AddITSConnection(secondConnection, secondConnectionIndex, laneIndex);
            }
        }
    }

    private void AddITSConnection(ERConnection connection, int connectionIndex, int laneIndex, bool reverse = false)
    {
        var data = connection.GetLaneData(connectionIndex, laneIndex);
        if (data == null) return;

        foreach (var laneConnector in data)
        {
            var laneFromPoint = reverse ? laneConnector.points.Last() : laneConnector.points.First();
            var laneToPoint = reverse ? laneConnector.points.First() : laneConnector.points.Last();
            var laneFrom = tsMainManager.lanes.FindNearestLastPoint(laneFromPoint);
            var laneTo = tsMainManager.lanes.FindNearestFirstPoint(laneToPoint);
            var points = (reverse ? laneConnector.points.Reverse() : laneConnector.points).ToArray();
            tsMainManager.AddConnector<TSLaneConnector>(laneFrom, laneTo, points);
        }
    }

    public ERRoad[] GetRoadObjects()
    {
        ERRoad[] roadObjects = Array.FindAll(roadNetwork.GetRoadObjects(), r => !r.GetRoadType().roadTypeName.Equals("Footpath"));
        return roadObjects;
    }

    public ERRoad[] GetFootpathObjects()
    {
        ERRoad[] roadObjects = Array.FindAll(roadNetwork.GetRoadObjects(), r => r.GetRoadType().roadTypeName.Equals("Footpath"));
        return roadObjects;
    }

    private ERConnection GetAttachedERConnectionIfAny(ERRoad currentRoad, int markerIndex, float maxDistance = 3f)
    {
        ERConnection[] connections = roadNetwork.GetConnections();
        foreach (ERConnection connection in connections)
        {
            float distance = (connection.gameObject.transform.position - currentRoad.GetMarkerPosition(markerIndex)).magnitude;
            Debug.Log("Conn: " + connection.gameObject.transform.position.ToString());
            Debug.Log("Marker: idx=" + markerIndex + ", " + currentRoad.GetMarkerPosition(markerIndex).ToString());
            Debug.Log(distance);

            if (distance <= maxDistance)
            {
                return connection;
            }
        }

        return null;
    }

    private ERRoad GetAttachedRoadIfAny(out int splinePointIndex, ERRoad[] roads, ERRoad road, int markerIndex, float maxDistance = 3f)
    {
        foreach (ERRoad neighbouringRoad in roads)
        {
            if (neighbouringRoad == road) continue;
            Vector3 startMarkerPos = neighbouringRoad.GetMarkerPosition(0);
            Vector3 endMarkerPos = neighbouringRoad.GetMarkerPosition(neighbouringRoad.GetMarkerCount() - 1);

            Vector3 connectionPos = road.GetMarkerPosition(markerIndex);
            float distanceToStartMarker = (startMarkerPos - connectionPos).magnitude;
            float distanceToEndMarker = (endMarkerPos - connectionPos).magnitude;

            if (distanceToStartMarker <= maxDistance * 2 || distanceToEndMarker <= maxDistance * 2)
            {
                splinePointIndex = -1;
                return null;
            }

            for (int i = 0; i < neighbouringRoad.GetSplinePointsCenter().Length; i++)
            {
                {
                    Vector3 splinePoint = neighbouringRoad.GetSplinePointsCenter()[i];
                    float distance = (splinePoint - connectionPos).magnitude;

                    if (distance <= maxDistance)
                    {
                        splinePointIndex = i;
                        return neighbouringRoad;
                    }
                }
            }
        }

        splinePointIndex = -1;
        return null;
    }

    public static Vector3 FindIntersectionOnYPlane(Vector3 line1Start, Vector3 line1End, Vector3 line2Start, Vector3 line2End)
    {
        (float intX, float intY) = FindIntersection(line1Start.x, line1Start.z, line1End.x, line1End.z, line2Start.x, line2Start.z, line2End.x, line2End.z);
        return new Vector3(intX, 0, intY);
    }

    public static Tuple<float, float> FindIntersection(float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4)
    {
        // Check if the lines are parallel
        float det = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);

        if (Math.Abs(det) < 1e-10)
        {
            // Lines are parallel or coincident
            return null;
        }

        // Calculate the intersection point
        float intersectionX = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / det;
        float intersectionY = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / det;

        return Tuple.Create(intersectionX, intersectionY);
    }
}
