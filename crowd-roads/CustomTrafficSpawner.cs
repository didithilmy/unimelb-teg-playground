using System.Collections;
using System.Collections.Generic;
using ITS.AI;
using UnityEngine;

public class CustomTrafficSpawner : MonoBehaviour
{
    public int secondsBetweenCars = 1;
    public TSMainManager tsMainManager;
    [SerializeField] public TSTrafficSpawner.TSSpawnVehicles[] cars;

    private GameObject trafficCarsContainer;
    private List<TSTrafficAI> trafficCars = new List<TSTrafficAI>();
    private List<Vector3> trafficCarPositions = new List<Vector3>();
    private float interpolationPeriod = 0;
    private bool enabled = false;

    void Start()
    {
        if (tsMainManager == null)
            tsMainManager = FindObjectOfType(typeof(TSMainManager)) as TSMainManager;

        trafficCarsContainer = new GameObject("TrafficCarsContainer");
    }

    void Update()
    {
        if (interpolationPeriod >= secondsBetweenCars && enabled)
        {
            //Do Stuff
            interpolationPeriod = 0;
            AddCar();
        }
        interpolationPeriod += UnityEngine.Time.deltaTime;
    }

    public void StartSpawner()
    {
        trafficCars = new List<TSTrafficAI>();
        trafficCarPositions = new List<Vector3>();
        enabled = true;
    }

    public void AddCar()
    {
        int selectedCarIndex = Random.Range(0, cars.Length - 1);
        GameObject carPrefab = cars[selectedCarIndex].cars;
        GameObject trafficAiGameObject = Instantiate(carPrefab);
        trafficAiGameObject.transform.parent = trafficCarsContainer.transform;

        TSTrafficAI trafficAi = trafficAiGameObject.GetComponent<TSTrafficAI>();
        trafficAi.Setlanes(tsMainManager.lanes);
        trafficAi.SetIsMultithreading(false); // TODO change

        int laneIndex = 0; // TODO change
        int pointIndex = 0; // TODO change
        var bounds = TSTrafficSpawner.CarSize(trafficAiGameObject);
        float carLength = bounds.size.z + 3;

        // TODO check if vehicle type is allowed on lane

        var reservedPoints = new Queue<TSTrafficAI.TSReservedPoints>();
        bool spawnAllowed = tsMainManager.lanes[laneIndex].TryToReserve(trafficAi, pointIndex, carLength + carLength / 2f, ref reservedPoints);

        Debug.Log("Called!");
        if (!spawnAllowed)
        {
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

}
