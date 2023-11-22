using System;
using System.Collections.Generic;
using ITS.AI;
using ITS.Utils;
using UnityEngine;
using KaimiraGames;

public class CustomTrafficSpawner : MonoBehaviour
{
    [System.Serializable]
    public class VehicleConfig
    {
        public GameObject carPrefab;
        public int frequency = 1;
    }

    public float secondsBetweenCars = 1f;
    public float radius = 1f;
    public float height = 0.5f;
    public TSMainManager tsMainManager;
    [SerializeField] public VehicleConfig[] vehicles;

    private WeightedList<VehicleConfig> vehiclesWeightedList = new();
    private GameObject trafficCarsContainer;
    private List<TSTrafficAI> trafficCars = new List<TSTrafficAI>();
    private List<Vector3> trafficCarPositions = new List<Vector3>();
    private float interpolationPeriod = 0;
    private bool spawnerEnabled = false;

    void Start()
    {
        if (tsMainManager == null)
            tsMainManager = FindObjectOfType(typeof(TSMainManager)) as TSMainManager;

        trafficCarsContainer = new GameObject("TrafficCarsContainer");
        trafficCarsContainer.transform.parent = transform;

        foreach (VehicleConfig vehicle in vehicles)
        {
            vehiclesWeightedList.Add(vehicle, vehicle.frequency);
        }
    }

    void Update()
    {
        if (interpolationPeriod >= secondsBetweenCars && spawnerEnabled)
        {
            //Do Stuff
            interpolationPeriod = 0;
            AddCar();
        }
        interpolationPeriod += UnityEngine.Time.deltaTime;
    }

    public void DestroyAllCars()
    {
        trafficCars.Clear();
        trafficCarPositions.Clear();
        foreach (Transform child in trafficCarsContainer.transform)
        {
            TSTrafficAI trafficAi = child.gameObject.GetComponent<TSTrafficAI>();
            trafficAi.Disable();
            Destroy(child.gameObject);
        }
    }

    public void StartSpawner()
    {
        trafficCars = new List<TSTrafficAI>();
        trafficCarPositions = new List<Vector3>();
        spawnerEnabled = true;
    }

    public void StopSpawner()
    {
        spawnerEnabled = false;
    }

    public void AddCar()
    {
        GameObject carPrefab = vehiclesWeightedList.Next().carPrefab;
        var vehicleType = carPrefab.GetComponent<TSTrafficAI>().myVehicleType;
        GetRandomLaneAndPointWithinArea(vehicleType, out int laneIndex, out int pointIndex);

        GameObject trafficAiGameObject = Instantiate(carPrefab);
        trafficAiGameObject.transform.parent = trafficCarsContainer.transform;

        TSTrafficAI trafficAi = trafficAiGameObject.GetComponent<TSTrafficAI>();
        trafficAi.Setlanes(tsMainManager.lanes);
        trafficAi.SetIsMultithreading(false); // TODO change

        var bounds = TSTrafficSpawner.CarSize(trafficAiGameObject);
        float carLength = 0; // bounds.size.z;

        // TODO check if vehicle type is allowed on lane

        var reservedPoints = new Queue<TSTrafficAI.TSReservedPoints>();
        bool spawnAllowed = tsMainManager.lanes[laneIndex].TryToReserve(trafficAi, pointIndex, carLength, ref reservedPoints);

        if (!spawnAllowed)
        {
            Debug.Log("Cannot spawn at laneIndex=" + laneIndex + ", pointIndex=" + pointIndex);
            Destroy(trafficAi.gameObject);
            return;
        }

        trafficAi.ReservedPointsEnqueue(reservedPoints);

        int pointIndexOffset = reservedPoints.Count - 1;
        var newPointIndex = pointIndex + pointIndexOffset / 2;

        SetCarPositionAndRotation(laneIndex, newPointIndex, trafficAi.Transform);
        trafficCars.Add(trafficAi);

        var currentWaypoint = pointIndex + pointIndexOffset - 1;
        var previousWaypoint = pointIndex;
        var newPreviousWaypointIndex = pointIndex + pointIndexOffset;
        trafficAi.InitializeWaypointsData(tsMainManager.lanes[laneIndex], newPreviousWaypointIndex, currentWaypoint, previousWaypoint, true);

        trafficAi.Enable();
    }

    private void SetCarPositionAndRotation(int laneIndex, int newPointIndex, Transform carTransform)
    {
        var respawnAltitude = 0.03f; // TODO change
        var tsPoints = tsMainManager.lanes[laneIndex].points[newPointIndex];
        var pointPosition = tsPoints.point;
        carTransform.position = pointPosition + Vector3.up * respawnAltitude;
        var nextPoint = tsMainManager.lanes[laneIndex].points[newPointIndex + 1];
        var nextPointPosition = nextPoint.point;
        var forward = nextPointPosition - pointPosition;
        carTransform.rotation = Quaternion.LookRotation(forward);
    }

    private void GetRandomLaneAndPointWithinArea(TSLaneInfo.VehicleType vehicleType, out int laneIndex, out int pointIndex)
    {
        List<(TSLaneInfo, TSPoints)> pointsWithinRadius = new List<(TSLaneInfo, TSPoints)>();
        foreach (TSLaneInfo lane in tsMainManager.lanes)
        {
            if (!lane.HasVehicleType(vehicleType))
                continue;

            foreach (TSPoints point in lane.Points)
            {
                Vector3 planeVector = transform.position - point.point;
                planeVector.y = 0;
                bool withinPlaneRadius = planeVector.magnitude <= radius;

                float heightDiff = Math.Abs(transform.position.y - point.point.y);
                bool withinHeight = heightDiff <= height;

                if (withinHeight && withinPlaneRadius) pointsWithinRadius.Add((lane, point));
            }
        }

        int randomIndex = UnityEngine.Random.Range(0, pointsWithinRadius.Count - 1);
        (TSLaneInfo chosenLane, TSPoints chosenPoint) = pointsWithinRadius[randomIndex];
        laneIndex = tsMainManager.lanes.FindIndex(chosenLane);
        pointIndex = chosenLane.Points.FindIndex(chosenPoint);
    }
}
