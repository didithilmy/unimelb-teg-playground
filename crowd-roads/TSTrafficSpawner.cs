using System;
using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using ITS.AI;
using Object = UnityEngine.Object;
using Random = UnityEngine.Random;

public class TSTrafficSpawner : MonoBehaviour
{
    [System.Serializable]
    public class TransformsSpawningCheck
    {
        public Transform transform;
        public float initialNotSpawningRadius = 10f;
        float sqrRadius = 0;
        float lastinitialNotSpawningRadius = 0;

        public Vector3 Position { get; private set; }
        public float InitialNotSpawningRadiusSQR
        {
            get
            {
                if (initialNotSpawningRadius != lastinitialNotSpawningRadius)
                {
                    sqrRadius = initialNotSpawningRadius * initialNotSpawningRadius;
                    lastinitialNotSpawningRadius = initialNotSpawningRadius;
                }

                return sqrRadius;
            }
        }

        public void UpdatePosition()
        {
            Position = transform.position;
        }
    }

    public class OtherSpawners
    {
        public TSTrafficSpawner spawnerReference;
        public bool isInRange = false;
    }

    [System.Serializable]
    public class TSSpawnVehicles
    {
        public GameObject cars;
        public int frequency = 1;
    }

    public struct PointsIndex
    {
        public int lane;
        public int point;

        public PointsIndex(int l, int p)
        {
            lane = l;
            point = p;
        }
    }

    #region public members

    /// <summary>
    /// The initialize on start.  If enabled the spawner would be initialized when the Awake is called.  If not it wont be initialized and
    /// The spawner would need to be initialized by script.
    /// </summary>
    public bool initializeOnStart = true;

    /// <summary>
    /// The cars.  This is the array that contains the source traffic cars that would be used to spawn on the scene.
    /// </summary>
    [SerializeField] public TSSpawnVehicles[] cars;

    /// <summary>
    /// The total amount of cars.  This would be the max amount of cars the pool would have.
    /// </summary>
    public int totalAmountOfCars = 50;

    /// <summary>
    /// The amount of cars that would  be on the scene.  This is the maximum amount of cars on the scene at the same time.
    /// </summary>
    public int amount = 50;

    /// <summary>
    /// The max distance from the spawner object the cars are spawned into, if the traffic cars are farther from this
    /// distance the cars would be disabled and respawned within this distance
    /// </summary>
    public float maxDistance = 150f;

    /// <summary>
    /// The offset.  This is the offset to make the area for spawning cars, it is the max distance minus this offset what
    /// makes the spawning area or radius
    /// </summary>
    public float offset = 140f;

    /// <summary>
    /// The closer range.  This is to make a callback triggered when the traffic car or pedestrians is near the spawning object
    /// from certain distance, usefull to activate other stuff on the traffic car or AI
    /// </summary>
    public float closerRange = 25f;

    /// <summary>
    /// The refresh time for spawning cars.
    /// </summary>
    public float refreshTime = 0.02f;

    /// <summary>
    /// The manager system which contains all the lanes info.
    /// </summary>
    public TSMainManager manager;


    /// <summary>
    /// The unused cars position.
    /// </summary>
    public Vector3 unusedCarsPosition = new Vector3(50000, 50000, 50000);

    /// <summary>
    /// The respawn if flipped.
    /// </summary>
    public bool respawnIfUpSideDown = false;

    /// <summary>
    /// The respawn up side down timer.
    /// </summary>
    public float respawnUpSideDownTime = 2f;

    /// <summary>
    /// The respawn altitude.  This is the altitude from the spawning point the car would get spanwed to.
    /// </summary>
    public float respawnAltitude = 0.3f;

    /// <summary>
    /// The disbale multi threading.
    /// </summary>
    public bool disableMultiThreading = false;

    /// <summary>
    /// The global point offset.  This would be the offset of the world with respect to the origin, this is useful in case you are in the need of having to shift the worlds game objects position
    /// to avoid floating precision issues on the physics.  The cars wont get moved automatically by the spawner to the new offset, this needs to be done separately.
    /// </summary>
    public Vector3 globalPointOffset = Vector3.zero;

    /// <summary>
    /// The cars checked per frame.  This would be the amount of cars that would be checked to see if they are outside the spawning are to despawn them
    /// </summary>
    public int carsCheckedPerFrame = 50;

    /// <summary>
    /// The initial not spawning radius.  This would be a radius that the spawner would check aroung its own position to avoid spanwing cars initially over the center or inside this
    /// radius, so you would be able to avoid cars to get spawned into the players car.
    /// </summary>
    public float initialNotSpawningRadius = 10f;

    /// <summary>
    /// The transform spawning check.  The spawner would check against all the listed Transforms to avoid spawning cars from their position with the radius given for each transform.
    /// </summary>
    [SerializeField] public TransformsSpawningCheck[] transformSpawningCheck = new TransformsSpawningCheck[0];

    [HideInInspector] public bool carsArePrefabs = true;

    #endregion

    #region private members

    /// <summary>
    /// The traffic volumes.
    /// </summary>
    private TSTrafficVolume[] trafficVolumes;

    /// <summary>
    /// The traffic cars reference.
    /// </summary>
    private TSTrafficAI[] trafficCars = new TSTrafficAI[0];


    /// <summary>
    /// The traffic cars transform reference.
    /// </summary>
    private Transform[] trafficCarsTransform;

    /// <summary>
    /// The traffic cars positions vector.
    /// </summary>
    private Vector3[] trafficCarsPositions = new Vector3[0];

    /// <summary>
    /// The traffic cars far indexes.
    /// </summary>
    private bool[] trafficCarsFarIndexes;

    /// <summary>
    /// The index of the points.
    /// </summary>
    PointsIndex[] pointsIndex = new PointsIndex[100];

    /// <summary>
    /// The next action time.
    /// </summary>
    private float nextActionTime = 0f;

    /// <summary>
    /// My position.
    /// </summary>
    private Vector3 myPosition = Vector3.zero;
    // Use this for initialization

#if UNITY_EDITOR || (!UNITY_METRO && !UNITY_WP8)

    /// <summary>
    /// The threads.
    /// </summary>
    private System.Threading.Thread[] threads;

    /// <summary>
    /// The job available.
    /// </summary>
    private AutoResetEvent[] jobAvailable;

    /// <summary>
    /// The thread idle.
    /// </summary>
    private ManualResetEvent[] threadIdle;

#endif

#if !UNITY_EDITOR && (UNITY_WP8 || UNITY_METRO)
	LegacySystem.Thread[] threads;
#endif

    /// <summary>
    /// The threads count.
    /// </summary>
    private int threadsCount = 0;

    /// <summary>
    /// The close.
    /// </summary>
    private bool close = false;

    /// <summary>
    /// The lock2.  This is used to sync the threads
    /// </summary>
    private Object lock2 = new Object();


    /// <summary>
    /// The current volume.
    /// </summary>
    private int currentVolume = 0;

    /// <summary>
    /// The trafficar last added.
    /// </summary>
    private int trafficarLastAdded = 0;

    /// <summary>
    /// The total far cars.
    /// </summary>
    private int _totalFarCars = 0;


    /// <summary>
    /// The max distance SQR max.
    /// </summary>
    private float maxDistanceSQRMax = 0f;

    /// <summary>
    /// The max distance SQR minimum.
    /// </summary>
    private float maxDistanceSQRMin = 0f;

    private GameObject trafficCarsContainer;
    private Transform trafficCarsParent;

    public static TSTrafficSpawner mainInstance;


    private OtherSpawners[] otherSpawners;
    private bool otherSpawnersPresent = false;

    private TSEventTrigger[] eventTriggers;
    private bool weHaveEventTriggers = false;
    private bool _Initialized = false;
    private SynchronizationContext _mainThread;
    private int _oldAmount;
    #endregion


    #region properties

    /// <summary>
    /// Gets or sets the max distance.  Use this for changing the spawner max distance at runtime by script, since
    /// this distance is converted into square distance for better performance calculations.
    /// </summary>
    /// <value>The max distance.</value>
    public float MaxDistance
    {
        get { return maxDistance; }
        set
        {
            maxDistance = value;
            maxDistanceSQRMax = (maxDistance + offset) * (maxDistance + offset);
            maxDistanceSQRMin = (maxDistance - offset) * (maxDistance - offset);
        }
    }

    /// <summary>
    /// Gets or sets the offset.  Use this for changing the spawner offset at runtime by script, since this offset is used 
    /// to talculate the min distance in squared values for better perfomance calculations.
    /// </summary>
    /// <value>The offset.</value>
    public float Offset
    {
        get { return offset; }
        set
        {
            offset = value;
            maxDistanceSQRMax = (maxDistance + offset) * (maxDistance + offset);
            maxDistanceSQRMin = (maxDistance - offset) * (maxDistance - offset);
        }
    }

    /// <summary>
    /// Gets the traffic cars.
    /// </summary>
    /// <value>The traffic cars.</value>
    public TSTrafficAI[] TrafficCars
    {
        get { return trafficCars; }
    }

    /// <summary>
    /// Gets the total far cars.
    /// </summary>
    /// <value>The total far cars.</value>
    public int totalFarCars
    {
        get { return _totalFarCars; }
    }

    /// <summary>
    /// Gets the traffic cars transform.
    /// </summary>
    /// <value>The traffic cars transform.</value>
    public Transform[] TrafficCarsTransform
    {
        get { return trafficCarsTransform; }
    }

    /// <summary>
    /// Gets the traffic cars positions.
    /// </summary>
    /// <value>The traffic cars positions.</value>
    public Vector3[] TrafficCarsPositions
    {
        get { return trafficCarsPositions; }
    }

    public static float RespawnUpSideDownTime
    {
        get { return mainInstance.respawnUpSideDownTime; }
    }

    /// <summary>
    /// Gets or sets the amount.
    /// </summary>
    /// <value>The amount.</value>
    public int Amount
    {
        get { return amount; }
        set { amount = value; }
    }

    public Transform TrafficCarsParent
    {
        get { return trafficCarsParent; }
    }

    #endregion properties

    private void Start()
    {
        _mainThread = SynchronizationContext.Current;
        InitializeMultithreading();

        if (initializeOnStart)
        {
            InitializeMe();
        }
        else
        {
            trafficCars = new TSTrafficAI[0];
            trafficCarsPositions = new Vector3[0];
            trafficCarsFarIndexes = new bool[0];
        }
    }

    public void InitializeMe()
    {
        if (!enabled || _Initialized)
        {
            return;
        }

        myPosition = transform.position;
        GetEventTriggers();
        GetOtherSpawners();
        mainInstance = this;

        if (manager == null)
        {
            manager = FindObjectOfType(typeof(TSMainManager)) as TSMainManager;
        }

        trafficCarsContainer = new GameObject("TrafficCarsContainer");
        trafficCarsParent = trafficCarsContainer.transform;
        PopulateInitialPoints();
        UpdateSpawningCheckTransformsPositions();
        AddCarsStart();
        _Initialized = true;
    }


    private void GetEventTriggers()
    {
        eventTriggers = FindObjectsOfType<TSEventTrigger>();
        weHaveEventTriggers = eventTriggers != null && eventTriggers.Length != 0;

        for (int i = 0; i < eventTriggers.Length; i++)
        {
            eventTriggers[i].InitializeMe();
        }
    }

    private void GetOtherSpawners()
    {
        var tempSpawners = GameObject.FindObjectsOfType<TSTrafficSpawner>();
        otherSpawners = new OtherSpawners[tempSpawners.Length - 1];
        var otherSpCounter = 0;

        if (tempSpawners.Length <= 1)
        {
            return;
        }

        otherSpawnersPresent = true;
        for (int i = 0; i < tempSpawners.Length; i++)
        {
            if (tempSpawners[i] == this)
            {
                continue;
            }

            otherSpawners[otherSpCounter] = new OtherSpawners { spawnerReference = tempSpawners[i] };
            otherSpCounter++;
        }
    }

    private void PopulateInitialPoints()
    {
        while (currentPointIndex < pointsIndex.Length)
        {
            pointsIndex[currentPointIndex] = new PointsIndex(0, 0);
            currentPointIndex++;
        }

        currentPointIndex = 0;
    }

    private void AddCarsStart()
    {
        if (cars.Length == 0) return;
        if (totalAmountOfCars < amount) totalAmountOfCars = amount;
        maxDistanceSQRMax = (maxDistance + offset) * (maxDistance + offset);
        maxDistanceSQRMin = (maxDistance - offset) * (maxDistance - offset);
        trafficVolumes = FindObjectsOfType(typeof(TSTrafficVolume)) as TSTrafficVolume[];
        int evenTriggersCounter = 0;
        if (weHaveEventTriggers) evenTriggersCounter = eventTriggers.Length;
        int currentEnventTrigger = 0;
        bool dontCreateAgain = false;
        GameObject trafficAIGameObject = null;
        int selectedCar = 0;
        int pointIndex = 0;
        int laneIndex = 0;

        var frequencyAmount = 0;

        for (int i = 0; i < cars.Length; i++)
        {
            frequencyAmount += cars[i].frequency;
        }

        int tempAmount = (totalAmountOfCars < cars.Length
            ? (cars.Length < frequencyAmount + cars.Length ? frequencyAmount + cars.Length : cars.Length)
            : (totalAmountOfCars < frequencyAmount + cars.Length ? frequencyAmount + cars.Length : totalAmountOfCars));

        //This is to be able to use cars from the scene
        if (carsArePrefabs == false)
        {
            tempAmount = cars.Length;
            for (int i = 0; i < cars.Length; i++)
            {
                cars[i].frequency = 1;
            }
        }

        trafficCars = new TSTrafficAI[tempAmount];
        trafficCarsTransform = new Transform[tempAmount];
        trafficCarsFarIndexes = new bool[tempAmount];
        trafficCarsPositions = new Vector3[tempAmount];
        bool gotAllFrequency = false;
        int frequencyIndex = 0;
        float carLength = 0;

        for (int i = 0; i < tempAmount; i++)
        {
            if (!dontCreateAgain)
            {
                if (!gotAllFrequency)
                {
                    bool gotOne = false;
                    while (!gotOne)
                    {
                        gotOne = GetCarByFrequency(ref frequencyIndex, out selectedCar);
                    }

                    if (frequencyIndex >= cars.Length)
                    {
                        gotAllFrequency = true;
                    }
                }
                else
                {
                    selectedCar = Random.Range(0, cars.Length);
                }

                selectedCar = Mathf.Clamp(selectedCar, 0, cars.Length - 1);

                if (carsArePrefabs)
                {
                    trafficAIGameObject = Instantiate(cars[selectedCar].cars);
                }
                else
                {
                    trafficAIGameObject = cars[selectedCar].cars;
                    trafficAIGameObject.SetActive(true);
                }

                trafficAIGameObject.transform.parent = trafficCarsParent;
                var bounds = CarSize(trafficAIGameObject);
                laneIndex = Random.Range(0, manager.lanes.Length - 1);
                carLength = bounds.size.z + 3;
                pointIndex = Random.Range(0, manager.lanes[laneIndex].points.Length - 1);
            }

            if (pointIndex >= manager.lanes[laneIndex].points.Length - carLength)
            {
                laneIndex = Random.Range(0, manager.lanes.Length - 1);
                pointIndex = Random.Range(0, manager.lanes[laneIndex].points.Length - 1);
            }

            //code for checking the triggers
            if (weHaveEventTriggers)
            {
                while (currentEnventTrigger < evenTriggersCounter &&
                       !eventTriggers[currentEnventTrigger].spawnCarOnStartingPoint)
                {
                    currentEnventTrigger++;
                }

                if (currentEnventTrigger < evenTriggersCounter)
                {
                    laneIndex = eventTriggers[currentEnventTrigger].startingPoint.lane;
                    pointIndex = eventTriggers[currentEnventTrigger].startingPoint.point;
                }
            }

            var pointIndexOffset = 0;
            var checkFree =
                !((myPosition - manager.lanes[laneIndex].points[pointIndex].point + globalPointOffset).magnitude <
                  initialNotSpawningRadius);

            if (!CheckAgainstTransformList(manager.lanes[laneIndex].points[pointIndex].point + globalPointOffset))
            {
                checkFree = false;
            }

            if (i >= amount - 1)
            {
                checkFree = false;
            }

            if (!CheckTrafficVolume(out currentVolume,
                manager.lanes[laneIndex].points[pointIndex].point + globalPointOffset))
            {
                checkFree = false;
            }

            var trafficAI = trafficAIGameObject.GetComponent<TSTrafficAI>();

            if (manager.lanes[laneIndex].HasVehicleType(trafficAI.myVehicleType) == false)
            {
                checkFree = false;
            }

            var reservedPoints = new Queue<TSTrafficAI.TSReservedPoints>();

            if (checkFree)
            {
                checkFree = manager.lanes[laneIndex].TryToReserve(trafficAI, pointIndex, carLength + carLength / 2f, ref reservedPoints);
            }

            trafficAI.Setlanes(manager.lanes);
            trafficAI.SetIsMultithreading(threadsCount > 0);

            if (checkFree)
            {
                if (currentVolume != -1)
                {
                    trafficVolumes[currentVolume].carsOnThisSection.Add(trafficAI);
                }

                pointIndexOffset = reservedPoints.Count - 1;
                trafficAI.ReservedPointsEnqueue(reservedPoints);

                var newPointIndex = pointIndex + pointIndexOffset / 2;
                SetCarPositionAndRotation(laneIndex, newPointIndex, trafficAI.Transform);
                AddTrafficAI(ref trafficAI);
                trafficCarsPositions[i] = (trafficAI.Transform.position);
                var currentWaypoint = pointIndex + pointIndexOffset - 1;
                var previousWaypoint = pointIndex;
                var newPreviousWaypointIndex = pointIndex + pointIndexOffset;
                trafficAI.InitializeWaypointsData(manager.lanes[laneIndex], newPreviousWaypointIndex, currentWaypoint,
                    previousWaypoint, respawnIfUpSideDown);
                dontCreateAgain = false;
                trafficCarsFarIndexes[i] = false;
                if (AssignCarToEvenTrigger(trafficAI, currentEnventTrigger) == false)
                {
                    trafficAI.Enable();
                }
            }
            else
            {
                AddTrafficAI(ref trafficAI);
                trafficCarsPositions[i] = (trafficAI.Transform.position);
                trafficAI.Disable(true, true);
                trafficAI.Transform.position = unusedCarsPosition;
                trafficCarsFarIndexes[i] = true;
                _totalFarCars++;
                dontCreateAgain = false;
            }

            currentEnventTrigger++;
        }
    }

    private bool CheckAgainstTransformList(Vector3 point)
    {
        if (ReferenceEquals(transformSpawningCheck, null) || transformSpawningCheck.Length <= 0)
        {
            return true;
        }

        for (var i = 0; i < transformSpawningCheck.Length; i++)
        {
            if ((transformSpawningCheck[i].Position - point).sqrMagnitude < transformSpawningCheck[i].InitialNotSpawningRadiusSQR)
            {
                return false;
            }
        }

        return true;
    }

    private bool AssignCarToEvenTrigger(TSTrafficAI car, int currentEnventTrigger)
    {
        if (weHaveEventTriggers == false)
        {
            return false;
        }

        if (currentEnventTrigger < eventTriggers.Length)
        {
            eventTriggers[currentEnventTrigger].SetCar(car);
            return true;
        }

        return false;
    }

    private void OnEnable()
    {
        StopCoroutine(DelayedOnEnable());
        StartCoroutine(DelayedOnEnable());
    }

    private IEnumerator DelayedOnEnable()
    {
        yield return new WaitUntil(() => _Initialized);

        if (threadsCount != 0)
        {
            yield break;
        }

        StopCoroutine(CheckNearLanesSingleThread());
        StartCoroutine(CheckNearLanesSingleThread());
    }

    int currentAmountOfCar = 0;

    private bool GetCarByFrequency(ref int currentIndex, out int returnedIndex)
    {
        returnedIndex = 0;

        if (currentIndex >= cars.Length)
        {
            return true;
        }

        if (cars[currentIndex].frequency != 0 && currentAmountOfCar < cars[currentIndex].frequency)
        {
            returnedIndex = currentIndex;
            currentAmountOfCar++;
            return true;
        }

        currentIndex++;
        currentAmountOfCar = 0;
        return false;
    }


    private void AddTrafficAI(ref TSTrafficAI trafficAI)
    {
        trafficCars[trafficarLastAdded] = trafficAI;
        trafficCarsTransform[trafficarLastAdded] = trafficAI.Transform;
        trafficarLastAdded++;
    }

    private bool CheckTrafficVolume(out int volume, Vector3 point)
    {
        volume = -1;
        for (var i = 0; i < trafficVolumes.Length; i++)
        {
            if (trafficVolumes[i].Contains(point) == false)
            {
                continue;
            }

            if (trafficVolumes[i].AllowedToSpawnAtPoint() == false) return false;
            volume = i;
            return true;
        }

        return true;
    }

    private static Bounds CarSize(GameObject car)
    {
        var tempRotation = car.transform.rotation;
        var tempPosition = car.transform.position;
        car.transform.rotation = Quaternion.Euler(Vector3.zero);
        car.transform.position = Vector3.zero;
        var bounds = new Bounds(car.transform.position, Vector3.zero);
        var renderers = car.GetComponentsInChildren<Collider>();

        foreach (var renderer in renderers)
        {
            if (!renderer.isTrigger)
            {
                bounds.Encapsulate(renderer.bounds);
            }
        }

        car.transform.rotation = tempRotation;
        car.transform.position = tempPosition;

        return bounds;
    }


    private void Update()
    {
        //*************JUST TESTING CODE
        //        if (Input.GetKeyUp(KeyCode.A))
        //            InitializeMe();
        //*************JUST TESTING CODE

        UpdateCarPositions();
        UpdateSpawningCheckTransformsPositions();
        myPosition = transform.position;

        if (Time.time - nextActionTime > refreshTime)
        {
            nextActionTime = Time.time;
            CheckFarCarsSingleThread();

            if (threadsCount == 0)
            {
                AddCar();
            }
        }
    }

    private void UpdateSpawningCheckTransformsPositions()
    {
        foreach (var spawningCheck in transformSpawningCheck)
        {
            spawningCheck.UpdatePosition();
        }
    }

    /// <summary>
    /// Updates the car positions.
    /// </summary>
    private void UpdateCarPositions()
    {
        if (trafficCars != null)
        {
            for (var i = 0; i < trafficCars.Length; i++)
            {
                trafficCarsPositions[i] = trafficCarsTransform[i].position;
            }
        }
    }

    int laneIndex1 = 0;
    int pointIndex1 = 0;
    int currentPointIndex = 0;
    int checkNearLanesTimer = 0;

    private void CheckNearLanes()
    {
        //		int timer = 0;
        for (; laneIndex1 < manager.lanes.Length; laneIndex1++)
        {
            for (; pointIndex1 < manager.lanes[laneIndex1].points.Length; pointIndex1++)
            {
                float distance3 =
                    ((manager.lanes[laneIndex1].points[pointIndex1].point + globalPointOffset) - myPosition)
                    .sqrMagnitude;
                if (distance3 > maxDistanceSQRMin && distance3 < maxDistanceSQRMax &&
                    manager.lanes[laneIndex1].points[pointIndex1].ReservationID == 0)
                {
                    if (pointIndex1 + 3 < manager.lanes[laneIndex1].points.Length &&
                        manager.lanes[laneIndex1].points[pointIndex1 + 1].ReservationID == 0 &&
                        manager.lanes[laneIndex1].points[pointIndex1 + 2].ReservationID == 0 &&
                        manager.lanes[laneIndex1].points[pointIndex1 + 3].ReservationID == 0)
                    {
                        lock (lock2)
                        {
                            pointsIndex[currentPointIndex].lane = laneIndex1;
                            pointsIndex[currentPointIndex].point = pointIndex1;
                        }

                        IncreaseCurrentPointIndex();
                    }
                }

                ++checkNearLanesTimer;
                if (checkNearLanesTimer > 500)
                {
                    checkNearLanesTimer = 0;
                    return;
                }
            }

            pointIndex1 = 0;
        }

        if (laneIndex1 >= manager.lanes.Length - 1) laneIndex1 = 0;
    }

    /// <summary>
    /// Checks the far cars.  This method checks the cars distance and put them on the far cars array
    /// so the system can disable them and respawn on another near point.
    /// </summary>
    private void CheckFarCars()
    {
        for (int i = 0; i < trafficCarsPositions.Length; i++)
        {
            trafficCars[i].SetPointOffset(globalPointOffset);
            float distance = (trafficCarsPositions[i] - myPosition).sqrMagnitude;
            if (distance > maxDistanceSQRMax * 1.2f || !trafficCars[i].enabled)
            {
                if (!trafficCarsFarIndexes[i] && !CheckIfPositionIsInsideAnotherSpawner(trafficCarsPositions[i]))
                {
                    _totalFarCars++;
                    trafficCarsFarIndexes[i] = true;
                }
            }
            else
            {
                if (trafficCarsFarIndexes[i])
                {
                    _totalFarCars--;
                    trafficCarsFarIndexes[i] = false;
                }
            }

            if (distance > closerRange * closerRange)
            {
                if (trafficCars[currentFarCar].OnFarRange != null)
                    trafficCars[currentFarCar].OnFarRange();
            }
            else
            {
                if (trafficCars[currentFarCar].OnCloserRange != null)
                    trafficCars[currentFarCar].OnCloserRange();
            }
        }
    }

    private bool CheckIfPositionIsInsideAnotherSpawner(Vector3 carPosition)
    {
        if (!otherSpawnersPresent)
        {
            return false;
        }

        for (int i = 0; i < otherSpawners.Length; i++)
        {
            if (otherSpawners[i].spawnerReference.CheckIfPositionIsInSpawnArea(carPosition))
            {
                return true;
            }
        }

        return false;
    }

    private bool CheckIfPositionIsInSpawnArea(Vector3 position)
    {
        return (position - myPosition).sqrMagnitude < maxDistanceSQRMax;
    }

    IEnumerator CheckNearLanesSingleThread()
    {
        var counter = 0;
        while (true)
        {
            for (var w = 0; w < manager.lanes.Length; w++)
            {
                for (var i = 0; i < manager.lanes[w].points.Length; i++)
                {
                    var distance3 = (manager.lanes[w].points[i].point + globalPointOffset - myPosition).sqrMagnitude;
                    var insideSpawnArea = distance3 > maxDistanceSQRMin && distance3 < maxDistanceSQRMax;
                    if (insideSpawnArea && manager.lanes[w].points[i].ReservationID == 0)
                    {
                        pointsIndex[currentPointIndex].lane = w;
                        pointsIndex[currentPointIndex].point = i;
                        IncreaseCurrentPointIndex();
                    }

                    if (IncreaseCounter(ref counter, 250))
                    {
                        continue;
                    }

                    yield return null;
                }
            }
        }
    }

    private static bool IncreaseCounter(ref int counter, int max)
    {
        counter++;

        if (counter <= max)
        {
            return true;
        }

        counter = 0;
        return false;
    }

    private void IncreaseCurrentPointIndex()
    {
        currentPointIndex++;

        if (currentPointIndex >= pointsIndex.Length)
        {
            currentPointIndex = 0;
        }
    }

    int currentFarCar = 0;
    int time = 0;

    private void CheckFarCarsSingleThread()
    {
        for (; currentFarCar < trafficCarsPositions.Length; currentFarCar++)
        {
            trafficCars[currentFarCar].SetPointOffset(globalPointOffset);

            if (time > carsCheckedPerFrame)
            {
                time = 0;
                return;
            }

            var distance = (trafficCarsPositions[currentFarCar] - myPosition).sqrMagnitude;
            var notReservedForEventTrigger = trafficCars[currentFarCar].reservedForEventTrigger == false;
            var outSideSpawnArea = distance > maxDistanceSQRMax * 1.2f;
            var isInactiveInHierarchy = trafficCarsTransform[currentFarCar].gameObject.activeSelf == false;
            if (notReservedForEventTrigger && (outSideSpawnArea || isInactiveInHierarchy))
            {
                var notMarkedAsOutsideSpawnArea = trafficCarsFarIndexes[currentFarCar] == false;
                if (notMarkedAsOutsideSpawnArea &&
                    CheckIfPositionIsInsideAnotherSpawner(trafficCarsPositions[currentFarCar]) == false)
                {
                    trafficCarsFarIndexes[currentFarCar] = true;
                    _totalFarCars++;
                    trafficCars[currentFarCar].Disable(true, true);
                    trafficCarsTransform[currentFarCar].position = unusedCarsPosition;
                }
            }
            else if (trafficCarsFarIndexes[currentFarCar])
            {
                _totalFarCars--;
                trafficCarsFarIndexes[currentFarCar] = false;
            }

            if (distance > closerRange * closerRange)
            {
                trafficCars[currentFarCar].OnFarRange?.Invoke();
            }
            else
            {
                trafficCars[currentFarCar].OnCloserRange?.Invoke();
            }

            time++;
        }

        currentFarCar = 0;
        time = 0;
    }

    /// <summary>
    /// Checks the far cars loop.
    /// </summary>
    /// <param name="obj">Object.</param>
    //	void CheckFarCarsLoop (object obj)
    //	{
    //		while (true) {
    //			CheckFarCars ();
    //			if (close)
    //				break;
    //		}
    //	}
    private long fixedTimeStep;

    private long _startTime;
    private long maxTimeStep;
    private double nextActionTimeDouble;

    /// <summary>
    /// Checks the near lanes (loop - Multithreading).
    /// </summary>
    /// <param name="obj">Object.</param>
    private void MainLoop(object obj)
    {
        var hiResTimer = new HiResTimer();
        hiResTimer.Start();
        _startTime = hiResTimer.Ticks;
        var previous = _startTime;
        var lag = 0L;
        while (true)
        {
            var current = hiResTimer.Ticks;
            var elapsed = current - previous;
            if (elapsed > maxTimeStep)
            {
                elapsed = maxTimeStep;
            }

            previous = current;
            lag += elapsed;

            if (_Initialized)
            {
                try
                {
                    if (close) { break; }

                    ThreadUpdate(current);

                    while (lag >= fixedTimeStep)
                    {
                        if (close) { break; }

                        ThreadFixedUpdate();
                        lag -= fixedTimeStep;
                    }
                }
                catch (Exception e)
                {
                    // Debug.Log($"{e.Message}\n{e.StackTrace}");
                }
            }

#if (UNITY_EDITOR || (!UNITY_METRO && !UNITY_WP8 && !NETFX_CORE))
            Thread.Sleep(0);
#else
			LegacySystem.Thread.Sleep(0);
#endif

            if (close)
            {
                break;
            }

        }
    }

    private void ThreadUpdate(long current)
    {
        CheckNearLanes();
        if ((current / 10000000d) - (double)nextActionTimeDouble > (double)refreshTime)
        {
            nextActionTimeDouble = current / 10000000d;
            AddCar();
        }
    }

    private void ThreadFixedUpdate()
    {
        for (int i = 0; i < trafficCars.Length; i++)
        {
            if (trafficCars[i].Initialized && trafficCars[i].IsEnabled)
            {
                trafficCars[i].FixedUpdateMe();
            }
        }
    }

    /// <summary>
    /// Checks the both.
    /// </summary>
    /// <param name="obj">Object.</param>
    //	void CheckBoth (object obj)
    //	{
    //		while (true) {
    //			CheckNearLanes ();
    //#if (UNITY_EDITOR || (!UNITY_METRO && !UNITY_WP8 && !NETFX_CORE))
    //			Thread.Sleep(0);
    //#else
    //			LegacySystem.Thread.Sleep(0);
    //#endif
    //			if (close)
    //				break;
    //		}
    //	}

    /// <summary>
    /// Gets the index of the next far car.
    /// </summary>
    /// <returns>The next car far index.</returns>
    private int GetNextCarFarIndex()
    {
        var i = ITS.Utils.Random.Range(0, trafficCarsFarIndexes.Length);
        var counter = 0;
        while (counter < trafficCarsFarIndexes.Length)
        {
            if (trafficCarsFarIndexes[i])
            {
                return i;
            }

            i++;

            if (i >= trafficCarsFarIndexes.Length)
            {
                i = 0;
            }

            counter++;
        }

        return -1;
    }


    /// <summary>
    /// Gets the index of the next far car next to a specific index.
    /// </summary>
    /// <returns>The next car far index.</returns>
    /// <param name="currentIndex">Current index.</param>
    private int GetNextCarFarIndex(int currentIndex)
    {
        currentIndex++;
        for (int i = currentIndex; i < trafficCarsFarIndexes.Length; i++)
        {
            if (trafficCarsFarIndexes[i])
            {
                return i;
            }
        }

        return -1;
    }

    private void AddCar()
    {
        if (TryGetValidLaneAndPointIndexes(out var pointIndex, out var laneIndex) == false)
        {
            return;
        }

        if (TryGetCarIndexAvailableToSpawn(laneIndex, out var nextCarFar) == false)
        {
            return;
        }

        var newCurrentLane = manager.lanes[laneIndex];
        var carLength = trafficCars[nextCarFar].CarDepth;
        var AI = trafficCars[nextCarFar];
        if (AI.Initialized == false || AI.Spawning || AI.IsEnabled)
        {
            return;
        }

        var reservedPoints = new Queue<TSTrafficAI.TSReservedPoints>();

        if (newCurrentLane.TryToReserve(AI, pointIndex, carLength + carLength * 0.5f, ref reservedPoints) == false)
        {
            return;
        }

        AI.Spawning = true;
        AddCarToTrafficVolume(AI);
        var pointIndexOffset = reservedPoints.Count - 1;
        var newPointIndex = pointIndex + pointIndexOffset / 2;
        var currentWaypoint = pointIndex + pointIndexOffset;
        var previousWaypoint = pointIndex;
        AI.ReservedPointsEnqueue(reservedPoints);
        AI.InitializeWaypointsData(newCurrentLane, currentWaypoint, previousWaypoint, previousWaypoint, respawnIfUpSideDown);
        _mainThread.Send((d) =>
        {
            if (!Application.isPlaying)
            {
                return;
            }

            SetCarPositionAndRotation(laneIndex, newPointIndex, trafficCars[nextCarFar].Transform);
            trafficCarsPositions[nextCarFar] = trafficCars[nextCarFar].Transform.position;
            AI.Enable();
            AI.Spawning = false;
            trafficCarsFarIndexes[nextCarFar] = false;
        }, this);


        _totalFarCars--;
    }

    private bool TryGetValidLaneAndPointIndexes(out int pointIndex, out int laneIndex)
    {
        pointIndex = GetNewRandomIndexes(out laneIndex);
        var newCurrentLane = manager.lanes[laneIndex];
        var point = newCurrentLane.points[pointIndex];
        var pointPosition = point.point + globalPointOffset;
        var pointDistance = (myPosition - pointPosition).sqrMagnitude;
        if (newCurrentLane.HasFreeDensity == false) { return false; }
        var checkFree = CheckAgainstTransformList(pointPosition);
        checkFree &= CheckTrafficVolume(out currentVolume, pointPosition);
        checkFree &= CheckIfPositionIsInsideAnotherSpawner(pointPosition) == false;

        return !(pointDistance < maxDistanceSQRMin) && !(pointDistance > maxDistanceSQRMax) &&
               !point.IsReserved && checkFree;
    }

    private void AddCarToTrafficVolume(TSTrafficAI trafficAI)
    {
        if (currentVolume != -1)
        {
            trafficVolumes[currentVolume].carsOnThisSection.Add(trafficAI);
        }
    }

    private void SetCarPositionAndRotation(int laneIndex, int newPointIndex, Transform carTransform)
    {
        var tsPoints = manager.lanes[laneIndex].points[newPointIndex];
        var pointPosition = tsPoints.point + globalPointOffset;
        carTransform.position = pointPosition + Vector3.up * respawnAltitude;
        var nextPoint = manager.lanes[laneIndex].points[newPointIndex + 1];
        var nextPointPosition = nextPoint.point + globalPointOffset;
        var forward = nextPointPosition - pointPosition;
        carTransform.rotation = Quaternion.LookRotation(forward);
    }


    private int GetNewRandomIndexes(out int laneIndex)
    {
        var pointIndex = 0;
        laneIndex = 0;

        lock (lock2)
        {
            var pointer = ITS.Utils.Random.Range(0, pointsIndex.Length - 1);
            pointIndex = pointsIndex[pointer].point;
            laneIndex = pointsIndex[pointer].lane;
        }

        return pointIndex;
    }

    private bool TryGetCarIndexAvailableToSpawn(int laneIndex, out int nextCarFar)
    {
        nextCarFar = GetNextCarFarIndex();
        var carsSpawnedAmountExceeded = trafficCars.Length - _totalFarCars >= amount;
        var noCarsToSpawnAvailable = _totalFarCars == 0;
        var cantSpawnCars = carsSpawnedAmountExceeded || noCarsToSpawnAvailable;
        var dontSpawnCars = amount == 0;
        if (dontSpawnCars || cantSpawnCars)
        {
            return false;
        }

        return ValidateNextCarToSpawnIndex(laneIndex, ref nextCarFar);
    }


    public void DisableAllCars()
    {
        _oldAmount = amount;
        amount = 0;
        foreach (var trafficAI in trafficCars)
        {
            if (trafficAI.IsEnabled)
            {
                trafficAI.Disable();
            }
        }
    }

    public void UpdateCarAmountInstantly(int newAmount)
    {
        newAmount = Mathf.Clamp(newAmount, 0, totalAmountOfCars);
        amount = newAmount;
        if (trafficCars.Count(car => car.IsEnabled) <= newAmount)
        {
            return;
        }

        while (trafficCars.Count(car => car.IsEnabled) > newAmount)
        {
            var nextCar = trafficCars.First(car => car.IsEnabled);
            nextCar.Disable(true, true);
        }
    }

    public void EnableCars(int newAmount)
    {
        this.amount = newAmount;
    }

    public void EnableCars()
    {
        amount = _oldAmount;
    }

    private bool ValidateNextCarToSpawnIndex(int laneIndex, ref int nextCarFar)
    {
        while (true)
        {
            if (nextCarFar == -1)
            {
                return false;
            }

            if (manager.lanes[laneIndex].HasVehicleType(trafficCars[nextCarFar].myVehicleType))
            {
                return true;
            }

            nextCarFar = GetNextCarFarIndex(nextCarFar);
        }
    }

    /// <summary>
    /// Initialize the threads if they are available.
    /// </summary>
    private void InitializeMultithreading()
    {
        fixedTimeStep = Convert.ToInt64(Time.fixedDeltaTime * 10000000d);
        maxTimeStep = Convert.ToInt64(Time.maximumDeltaTime * 10000000d);

        threadsCount = System.Environment.ProcessorCount;
        if (disableMultiThreading)
            threadsCount = 0;
        //No point starting new threads for a single core computer
        if (threadsCount <= 1)
        {
            //						notThreading = true;
            threadsCount = 0;
            return;
        }

        threadsCount = Mathf.Clamp(threadsCount, 0, 1);
#if (UNITY_EDITOR || (!UNITY_METRO && !UNITY_WP8 && !NETFX_CORE))
        // array of events, which signal about available job
        jobAvailable = new AutoResetEvent[1];
        // array of events, which signal about available thread
        threadIdle = new ManualResetEvent[1];
        // array of threads
        threads = new Thread[1];

        jobAvailable[0] = new AutoResetEvent(false);
        threadIdle[0] = new ManualResetEvent(true);
        threads[0] = new Thread(new ParameterizedThreadStart(MainLoop));
        threads[0].IsBackground = false;
        threads[0].Start(0);
#else
		threads = new LegacySystem.Thread[1];
		threads[0] = new LegacySystem.Thread(new LegacySystem.ParameterizedThreadStart(CheckNearLanesLoop));
		threads [0].Start (0);
#endif
    }

    /// <summary>
    /// Close any threads if any.
    /// </summary>
    public void Close()
    {
#if (UNITY_EDITOR || (!UNITY_METRO && !UNITY_WP8 && !NETFX_CORE))
        //Exit all threads
        for (int i = 0; i < threadsCount; i++)
            jobAvailable[i].Set();

#endif
    }

    void OnDisable()
    {
        close = true;
    }

    void OnDestroy()
    {
        DisableAllCars();
        Destroy(trafficCarsContainer);
        close = true;
    }

    void OnDrawGizmos()
    {
        Gizmos.color = Color.green;
        Gizmos.DrawWireSphere(transform.position, maxDistance + offset);
        Gizmos.DrawWireSphere(transform.position, maxDistance - offset);
    }
}

public class HiResTimer
{
    System.Diagnostics.Stopwatch stopwatch;

    public HiResTimer()
    {
        stopwatch = new System.Diagnostics.Stopwatch();
        stopwatch.Reset();
    }

    public long ElapsedMilliseconds
    {
        get { return stopwatch.ElapsedMilliseconds; }
    }

    public long Ticks
    {
        get { return stopwatch.ElapsedTicks; }
    }

    public void Start()
    {
        if (!stopwatch.IsRunning)
        {
            stopwatch.Reset();
            stopwatch.Start();
        }
    }
    public void Stop()
    {
        stopwatch.Stop();
    }
}